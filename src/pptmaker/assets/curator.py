import hashlib
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pptmaker.assets.downloader import InvalidImage, VerifiedImage, download_image
from pptmaker.assets.models import AssetRecord, LicenseMode
from pptmaker.assets.providers import AssetProvider, AssetProviderError
from pptmaker.assets.repository import AssetRepository
from pptmaker.blueprint.models import DeckBlueprint


@dataclass(frozen=True)
class CurationResult:
    candidate_counts: dict[str, int]
    failures: dict[str, str]
    diagnostics: dict[str, dict[str, int]]


def _resolve(host: str) -> list[str]:
    return list(
        dict.fromkeys(
            item[4][0]
            for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        )
    )


class AssetCurator:
    def __init__(
        self,
        search: AssetProvider,
        repository: AssetRepository,
        destination_root: Path,
        *,
        downloader: Callable[..., VerifiedImage] = download_image,
        resolver: Callable[[str], list[str]] = _resolve,
        clock: Callable[[], datetime] | None = None,
    ):
        self.search = search
        self.repository = repository
        self.destination_root = Path(destination_root)
        self.downloader = downloader
        self.resolver = resolver
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def curate(
        self,
        project_id: str,
        blueprint: DeckBlueprint,
        license_mode: LicenseMode,
        *,
        page_ids: set[str] | None = None,
    ) -> CurationResult:
        if blueprint.project_id != project_id:
            raise ValueError("blueprint project does not match")
        counts = {}
        failures = {}
        diagnostics = {}
        for page in blueprint.pages:
            if page_ids is not None and page.page_id not in page_ids:
                continue
            if (
                page.visual.kind not in {"photo", "illustration"}
                or not page.asset_search_query.strip()
            ):
                continue
            try:
                candidates = self.search.search(
                    page.asset_search_query.strip(), 8
                )
            except AssetProviderError:
                failures[page.page_id] = "image search unavailable"
                self.repository.replace_candidates(
                    project_id,
                    blueprint.version,
                    page.page_id,
                    [],
                )
                self.repository.set_page_error(
                    project_id,
                    blueprint.version,
                    page.page_id,
                    failures[page.page_id],
                )
                diagnostics[page.page_id] = {
                    "searched": 0,
                    "download_failed": 0,
                    "validation_rejected": 0,
                    "usable": 0,
                }
                continue
            records = []
            rejected = 0
            download_failed = 0
            for candidate in candidates:
                identifier = hashlib.sha256(
                    (
                        page.page_id
                        + candidate.provider
                        + candidate.id
                    ).encode("utf-8")
                ).hexdigest()[:24]
                try:
                    record = AssetRecord(
                        **candidate.model_dump(exclude={"id"}),
                        id=identifier,
                        project_id=project_id,
                        blueprint_version=blueprint.version,
                        page_id=page.page_id,
                        license_mode=license_mode,
                        accessed_at=self.clock(),
                    )
                    verified = self.downloader(
                        record,
                        self.destination_root
                        / project_id
                        / str(blueprint.version)
                        / page.page_id,
                        self.resolver,
                    )
                except InvalidImage:
                    rejected += 1
                    continue
                except (ValueError, OSError):
                    download_failed += 1
                    continue
                records.append(
                    record.model_copy(
                        update={
                            "local_path": str(verified.path),
                            "content_hash": verified.content_hash,
                            "mime_type": verified.mime_type,
                            "byte_size": verified.byte_size,
                            "width": verified.width,
                            "height": verified.height,
                        }
                    )
                )
                if len(records) == 5:
                    break
            self.repository.replace_candidates(
                project_id,
                blueprint.version,
                page.page_id,
                records,
            )
            counts[page.page_id] = len(records)
            diagnostics[page.page_id] = {
                "searched": len(candidates),
                "download_failed": download_failed,
                "validation_rejected": rejected,
                "usable": len(records),
            }
            if not records:
                failures[page.page_id] = (
                    "未找到可安全下载的图片"
                    if candidates
                    else "未搜索到图片候选"
                )
            self.repository.set_page_error(
                project_id,
                blueprint.version,
                page.page_id,
                failures.get(page.page_id),
            )
        return CurationResult(counts, failures, diagnostics)
