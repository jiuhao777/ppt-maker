import json

import httpx
import pytest

from pptmaker.research.bocha import (
    BochaSearch,
    SearchAuthenticationError,
    SearchRateLimitError,
    SearchTimeoutError,
    SearchUnavailableError,
)
from pptmaker.research.contracts import SearchQuery


def response_payload():
    return {
        "code": 200,
        "data": {
            "webPages": {
                "value": [
                    {
                        "name": "DeepSeek 发布",
                        "url": "https://example.com/deepseek",
                        "snippet": "近期发布信息",
                        "summary": "摘要",
                        "siteName": "Example",
                        "datePublished": "2026-01-02T00:00:00Z",
                    }
                ]
            }
        },
    }


def test_bocha_uses_official_endpoint_and_bearer_key():
    def handler(request):
        assert str(request.url) == "https://api.bochaai.com/v1/web-search"
        assert request.headers["Authorization"] == "Bearer TEST_KEY"
        assert json.loads(request.content) == {
            "query": "中国大模型现状",
            "freshness": "oneYear",
            "summary": True,
            "count": 5,
        }
        return httpx.Response(200, json=response_payload())

    results = BochaSearch(transport=httpx.MockTransport(handler)).search(
        SearchQuery(query="中国大模型现状"),
        "TEST_KEY",
    )

    assert len(results) == 1
    assert results[0].provider == "bocha"
    assert results[0].site_name == "Example"


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, SearchAuthenticationError),
        (429, SearchRateLimitError),
        (503, SearchUnavailableError),
    ],
)
def test_bocha_maps_errors_without_response_body(status, error_type):
    adapter = BochaSearch(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status, text="Bearer TEST_KEY")
        )
    )

    with pytest.raises(error_type) as caught:
        adapter.search(SearchQuery(query="test"), "TEST_KEY")

    assert "TEST_KEY" not in str(caught.value)


def test_bocha_maps_timeout():
    def timeout(_request):
        raise httpx.ReadTimeout("secret")

    with pytest.raises(SearchTimeoutError):
        BochaSearch(transport=httpx.MockTransport(timeout)).search(
            SearchQuery(query="test"),
            "TEST_KEY",
        )


def test_bocha_rejects_malformed_response_safely():
    adapter = BochaSearch(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"data": "bad"})
        )
    )

    with pytest.raises(SearchUnavailableError) as caught:
        adapter.search(SearchQuery(query="test"), "TEST_KEY")

    assert str(caught.value) == "搜索服务返回了无效数据"


def test_bocha_deduplicates_urls():
    payload = response_payload()
    payload["data"]["webPages"]["value"] *= 2
    adapter = BochaSearch(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=payload)
        )
    )

    assert len(adapter.search(SearchQuery(query="test"), "TEST_KEY")) == 1
