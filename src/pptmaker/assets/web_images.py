from html.parser import HTMLParser
import json
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError

from pptmaker.assets.models import AssetCandidate
from pptmaker.assets.providers import AssetProviderError
from pptmaker.research.bocha import BochaSearch, SearchError
from pptmaker.research.contracts import SearchQuery
from pptmaker.security.fetcher import SafeFetchPolicy, safe_fetch_result


class _ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("property") in {
            "og:image",
            "twitter:image",
        }:
            self.urls.append(values.get("content"))
        elif tag == "img":
            self.urls.append(
                values.get("data-src") or values.get("src")
            )


class BochaWebImageProvider:
    def __init__(
        self,
        api_key: str,
        resolver,
        *,
        search=None,
        fetcher=safe_fetch_result,
    ):
        self.api_key = api_key
        self.resolver = resolver
        self.search_service = search or BochaSearch()
        self.fetcher = fetcher

    def search(self, query: str, count: int) -> list[AssetCandidate]:
        if not self.api_key:
            return []
        try:
            pages = self.search_service.search(
                SearchQuery(query=f"{query} 图片", count=min(count, 5)),
                self.api_key,
            )
        except SearchError as exc:
            raise AssetProviderError("unavailable") from exc
        candidates = []
        for page in pages[:3]:
            try:
                response = self.fetcher(
                    str(page.url),
                    self.resolver,
                    SafeFetchPolicy(
                        allowed_content_types=("text/html",),
                        max_response_bytes=2 * 1024 * 1024,
                        timeout_seconds=8,
                    ),
                )
            except Exception:
                continue
            parser = _ImageParser()
            try:
                parser.feed(response.content.decode("utf-8", "ignore"))
            except Exception:
                continue
            for index, value in enumerate(parser.urls):
                if not value:
                    continue
                image_url = urljoin(response.final_url, value)
                try:
                    candidates.append(
                        AssetCandidate(
                            id=f"bocha-{len(candidates)}-{index}",
                            provider="bocha-web",
                            original_url=image_url,
                            landing_url=str(page.url),
                            thumbnail_url=image_url,
                            license_status="UNKNOWN",
                            width=1600,
                            height=900,
                        )
                    )
                except (TypeError, ValidationError):
                    continue
                if len(candidates) == count:
                    return candidates
        return candidates


class _BingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag != "a" or "iusc" not in values.get("class", "").split():
            return
        try:
            item = json.loads(values.get("m", ""))
        except (TypeError, ValueError):
            return
        if isinstance(item, dict):
            self.items.append(item)


class BingImageProvider:
    endpoint = "https://cn.bing.com/images/async"

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 8,
    ):
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, count: int) -> list[AssetCandidate]:
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = client.get(
                    self.endpoint,
                    params={
                        "q": query,
                        "first": 0,
                        "count": max(1, min(count, 20)),
                        "cw": 1177,
                        "ch": 739,
                    },
                    headers={"User-Agent": "Mozilla/5.0 PPTMaker/1.0"},
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AssetProviderError("unavailable") from exc
        parser = _BingParser()
        parser.feed(response.text)
        candidates = []
        for index, item in enumerate(parser.items):
            original = item.get("murl")
            thumbnail = item.get("turl") or original
            landing = item.get("purl") or original
            if not original or not thumbnail:
                continue
            try:
                candidates.append(
                    AssetCandidate(
                        id=f"bing-{item.get('mid') or index}",
                        provider="bing-cn",
                        original_url=original,
                        landing_url=landing,
                        thumbnail_url=thumbnail,
                        license_status="UNKNOWN",
                        width=int(item.get("w") or 1600),
                        height=int(item.get("h") or 900),
                    )
                )
            except (TypeError, ValueError, ValidationError):
                continue
            if len(candidates) == count:
                break
        return candidates
