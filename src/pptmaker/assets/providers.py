import re
from typing import Protocol

import httpx
from pydantic import ValidationError

from pptmaker.assets.models import AssetCandidate


class AssetProviderError(RuntimeError):
    pass


class AssetProvider(Protocol):
    def search(self, query: str, count: int) -> list[AssetCandidate]: ...


def _license_status(value: str | None) -> str:
    normalized = (value or "").lower().replace("_", "-")
    if normalized in {"cc0", "pdm", "by", "by-sa"}:
        return "REUSABLE"
    if normalized:
        return "RESTRICTED"
    return "UNKNOWN"


def _request_json(
    endpoint: str,
    params: dict[str, object],
    transport: httpx.BaseTransport | None,
    timeout_seconds: float,
) -> dict:
    try:
        with httpx.Client(
            transport=transport,
            timeout=timeout_seconds,
            follow_redirects=False,
        ) as client:
            for attempt in range(2):
                response = client.get(endpoint, params=params)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                if attempt == 1:
                    category = (
                        "rate_limit"
                        if response.status_code == 429
                        else "unavailable"
                    )
                    raise AssetProviderError(category)
    except httpx.TimeoutException as exc:
        raise AssetProviderError("timeout") from exc
    except httpx.HTTPError as exc:
        raise AssetProviderError("unavailable") from exc
    if response.status_code >= 400:
        raise AssetProviderError("unavailable")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AssetProviderError("invalid_response") from exc
    if not isinstance(payload, dict):
        raise AssetProviderError("invalid_response")
    return payload


class OpenverseProvider:
    endpoint = "https://api.openverse.org/v1/images/"

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 15,
    ):
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, count: int) -> list[AssetCandidate]:
        payload = _request_json(
            self.endpoint,
            {"q": query[:200], "page_size": max(1, min(count, 20))},
            self.transport,
            self.timeout_seconds,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise AssetProviderError("invalid_response")
        candidates = []
        for item in results:
            if not isinstance(item, dict) or item.get("mature"):
                continue
            try:
                candidates.append(
                    AssetCandidate(
                        id=str(item["id"]),
                        provider="openverse",
                        original_url=item["url"],
                        landing_url=item["foreign_landing_url"],
                        thumbnail_url=item["thumbnail"],
                        creator=item.get("creator"),
                        license_name=_openverse_license_name(item),
                        license_url=item.get("license_url"),
                        license_status=_license_status(item.get("license")),
                        attribution=item.get("attribution") or "",
                        width=item["width"],
                        height=item["height"],
                    )
                )
            except (KeyError, TypeError, ValidationError):
                continue
        return candidates


def _openverse_license_name(item: dict) -> str | None:
    name = item.get("license")
    if not name:
        return None
    version = item.get("license_version")
    return f"{str(name).upper()} {version}".strip() if version else str(name).upper()


_HTML = re.compile(r"<[^>]+>")


def _metadata_value(metadata: object, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    item = metadata.get(key)
    if not isinstance(item, dict) or not item.get("value"):
        return None
    return _HTML.sub("", str(item["value"])).strip() or None


class WikimediaProvider:
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 15,
    ):
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, count: int) -> list[AssetCandidate]:
        payload = _request_json(
            self.endpoint,
            {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,
                "gsrlimit": max(1, min(count, 20)),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": 800,
            },
            self.transport,
            self.timeout_seconds,
        )
        query_data = payload.get("query", {})
        pages = query_data.get("pages", []) if isinstance(query_data, dict) else []
        if isinstance(pages, dict):
            pages = list(pages.values())
        if not isinstance(pages, list):
            raise AssetProviderError("invalid_response")
        candidates = []
        for page in pages:
            info_items = page.get("imageinfo", []) if isinstance(page, dict) else []
            if not info_items or not isinstance(info_items[0], dict):
                continue
            info = info_items[0]
            metadata = info.get("extmetadata")
            license_name = _metadata_value(metadata, "LicenseShortName")
            try:
                candidates.append(
                    AssetCandidate(
                        id=f"commons-{page['pageid']}",
                        provider="wikimedia",
                        original_url=info["url"],
                        landing_url=info["descriptionurl"],
                        thumbnail_url=info.get("thumburl") or info["url"],
                        creator=_metadata_value(metadata, "Artist"),
                        license_name=license_name,
                        license_url=_metadata_value(metadata, "LicenseUrl"),
                        license_status=_license_status(
                            _wikimedia_license_code(license_name)
                        ),
                        attribution=_metadata_value(metadata, "Credit") or "",
                        width=info["width"],
                        height=info["height"],
                    )
                )
            except (KeyError, TypeError, ValidationError):
                continue
        return candidates


def _wikimedia_license_code(value: str | None) -> str | None:
    normalized = (value or "").lower()
    if "public domain" in normalized:
        return "pdm"
    if "cc0" in normalized:
        return "cc0"
    if "by-sa" in normalized:
        return "by-sa"
    if "cc by" in normalized:
        return "by"
    return value


class FallbackAssetSearch:
    def __init__(self, primary: AssetProvider, secondary: AssetProvider):
        self.primary = primary
        self.secondary = secondary

    def search(self, query: str, count: int) -> list[AssetCandidate]:
        try:
            candidates = self.primary.search(query, count)
        except AssetProviderError:
            candidates = []
        if len(candidates) < count:
            try:
                candidates.extend(self.secondary.search(query, count))
            except AssetProviderError:
                if not candidates:
                    raise
        unique = []
        seen = set()
        for item in candidates:
            key = (str(item.landing_url), str(item.original_url))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) == count:
                break
        return unique
