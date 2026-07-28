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
        slot_ids: set[tuple[str, str]] | None = None,
    ) -> CurationResult:
        if blueprint.project_id != project_id:
            raise ValueError("blueprint project does not match")
        counts = {}
        failures = {}
        diagnostics = {}
        for page in blueprint.pages:
            if page_ids is not None and page.page_id not in page_ids:
                continue
            targets = [
                (slot.slot_id, slot.search_query)
                for slot in page.asset_slots
            ]
            if not targets and page.asset_search_query.strip():
                targets = [("hero", page.asset_search_query)]
            for slot_id, search_query in targets:
                if (
                    slot_ids is not None
                    and (page.page_id, slot_id) not in slot_ids
                ):
                    continue
                result_key = (
                    f"{page.page_id}:{slot_id}"
                    if page.asset_slots
                    else page.page_id
                )
                self._curate_slot(
                    project_id,
                    blueprint,
                    page.page_id,
                    slot_id,
                    search_query,
                    license_mode,
                    counts,
                    failures,
                    diagnostics,
                    result_key,
                )
        return CurationResult(counts, failures, diagnostics)

    def _curate_slot(
        self,
        project_id,
        blueprint,
        page_id,
        slot_id,
        search_query,
        license_mode,
        counts,
        failures,
        diagnostics,
        result_key,
    ) -> None:
            key = result_key
            try:
                candidates = self.search.search(
                    search_query.strip(), 8
                )
            except AssetProviderError:
                failures[key] = "image search unavailable"
                self.repository.replace_candidates(
                    project_id,
                    blueprint.version,
                    page_id,
                    [],
                    slot_id,
                )
                self.repository.set_page_error(
                    project_id,
                    blueprint.version,
                    key,
                    failures[key],
                )
                diagnostics[key] = {
                    "searched": 0,
                    "download_failed": 0,
                    "validation_rejected": 0,
                    "usable": 0,
                }
                return
            records = []
            rejected = 0
            download_failed = 0
            for candidate in candidates:
                identifier = hashlib.sha256(
                    (
                        page_id
                        + slot_id
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
                        page_id=page_id,
                        slot_id=slot_id,
                        license_mode=license_mode,
                        accessed_at=self.clock(),
                    )
                    verified = self.downloader(
                        record,
                        self.destination_root
                        / project_id
                        / str(blueprint.version)
                        / page_id
                        / slot_id,
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
                page_id,
                records,
                slot_id,
            )
            counts[key] = len(records)
            diagnostics[key] = {
                "searched": len(candidates),
                "download_failed": download_failed,
                "validation_rejected": rejected,
                "usable": len(records),
            }
            if not records:
                failures[key] = (
                    "未找到可安全下载的图片"
                    if candidates
                    else "未搜索到图片候选"
                )
            self.repository.set_page_error(
                project_id,
                blueprint.version,
                key,
                failures.get(key),
            )
