from typing import Literal

import httpx
from pydantic import BaseModel

from pptmaker.research.contracts import SearchQuery, SearchResult


class SearchError(RuntimeError):
    pass


class SearchAuthenticationError(SearchError):
    pass


class SearchRateLimitError(SearchError):
    pass


class SearchTimeoutError(SearchError):
    pass


class SearchUnavailableError(SearchError):
    pass


class SearchProbe(BaseModel):
    status: Literal["success", "failed"]
    error_type: str | None = None


def _raise_safe_status(status: int) -> None:
    if status in {401, 403}:
        raise SearchAuthenticationError("搜索 API Key 无效")
    if status == 429:
        raise SearchRateLimitError("搜索服务当前限流")
    if status in {408, 504}:
        raise SearchTimeoutError("搜索服务超时")
    if status >= 400:
        raise SearchUnavailableError("搜索服务暂时不可用")


def _parse_results(payload: object) -> list[SearchResult]:
    if not isinstance(payload, dict):
        raise SearchUnavailableError("搜索服务返回了无效数据")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise SearchUnavailableError("搜索服务返回了无效数据")
    web_pages = data.get("webPages", {})
    if not isinstance(web_pages, dict):
        raise SearchUnavailableError("搜索服务返回了无效数据")
    values = web_pages.get("value", [])
    if not isinstance(values, list):
        raise SearchUnavailableError("搜索服务返回了无效数据")

    results = []
    seen = set()
    try:
        for item in values:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not url or url in seen:
                continue
            result = SearchResult(
                title=item.get("name") or item.get("title") or "未命名来源",
                url=url,
                snippet=item.get("snippet") or "",
                summary=item.get("summary") or "",
                site_name=item.get("siteName") or "未知来源",
                published_at=item.get("datePublished"),
                provider="bocha",
            )
            seen.add(url)
            results.append(result)
    except (TypeError, ValueError) as exc:
        raise SearchUnavailableError("搜索服务返回了无效数据") from exc
    return results


class BochaSearch:
    endpoint = "https://api.bochaai.com/v1/web-search"

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 15.0,
    ):
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    def search(
        self,
        query: SearchQuery,
        api_key: str,
    ) -> list[SearchResult]:
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "query": query.query,
                        "freshness": query.freshness,
                        "summary": True,
                        "count": query.count,
                    },
                )
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError("搜索服务超时") from exc
        except httpx.HTTPError as exc:
            raise SearchUnavailableError("搜索服务暂时不可用") from exc
        _raise_safe_status(response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchUnavailableError("搜索服务返回了无效数据") from exc
        if isinstance(payload, dict) and payload.get("code") not in {None, 200}:
            raise SearchUnavailableError("搜索服务暂时不可用")
        return _parse_results(payload)

    def probe(self, api_key: str) -> SearchProbe:
        try:
            self.search(SearchQuery(query="连接测试", count=1), api_key)
        except SearchError as exc:
            return SearchProbe(
                status="failed",
                error_type=type(exc).__name__,
            )
        return SearchProbe(status="success")
