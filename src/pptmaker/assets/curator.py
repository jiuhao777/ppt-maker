import hashlib
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pptmaker.assets.downloader import VerifiedImage, download_image
from pptmaker.assets.models import AssetRecord, LicenseMode
from pptmaker.assets.providers import AssetProvider, AssetProviderError
from pptmaker.assets.repository import AssetRepository
from pptmaker.blueprint.models import DeckBlueprint


@dataclass(frozen=True)
class CurationResult:
    candidate_counts: dict[str, int]
    failures: dict[str, str]


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
    ) -> CurationResult:
        if blueprint.project_id != project_id:
            raise ValueError("blueprint project does not match")
        counts = {}
        failures = {}
        for page in blueprint.pages:
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
                continue
            records = []
            verification_failed = False
            for candidate in candidates:
                if (
                    license_mode == "STRICT"
                    and candidate.license_status != "REUSABLE"
                ):
                    continue
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
                except (ValueError, OSError):
                    verification_failed = True
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
                if len(records) == 3:
                    break
            self.repository.replace_candidates(
                project_id,
                blueprint.version,
                page.page_id,
                records,
            )
            counts[page.page_id] = len(records)
            if verification_failed:
                failures[page.page_id] = (
                    "some candidates failed verification"
                )
            self.repository.set_page_error(
                project_id,
                blueprint.version,
                page.page_id,
                failures.get(page.page_id),
            )
        return CurationResult(counts, failures)
