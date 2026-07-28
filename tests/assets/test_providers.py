import httpx
import pytest

from pptmaker.assets.providers import (
    AssetProviderError,
    FallbackAssetSearch,
    JsonImageProvider,
    OpenverseProvider,
    ProviderChain,
    WikimediaProvider,
    query_variants,
)


def test_openverse_maps_traceable_reusable_asset():
    def handler(request):
        assert request.url.params["q"] == "factory"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "ov1",
                        "url": "https://images.example/full.jpg",
                        "thumbnail": "https://images.example/thumb.jpg",
                        "foreign_landing_url": "https://source.example/work",
                        "creator": "Alice",
                        "license": "by",
                        "license_version": "4.0",
                        "license_url": "https://creativecommons.org/licenses/by/4.0/",
                        "attribution": "Factory by Alice",
                        "width": 1600,
                        "height": 900,
                        "mature": False,
                    }
                ]
            },
            request=request,
        )

    result = OpenverseProvider(
        transport=httpx.MockTransport(handler)
    ).search("factory", 3)

    assert len(result) == 1
    assert result[0].license_status == "REUSABLE"
    assert result[0].creator == "Alice"
    assert str(result[0].landing_url) == "https://source.example/work"


def test_openverse_rejects_mature_and_invalid_items():
    def handler(request):
        item = {
            "id": "ov1",
            "url": "https://images.example/full.jpg",
            "thumbnail": "https://images.example/thumb.jpg",
            "foreign_landing_url": "https://source.example/work",
            "license": "by-nc",
            "width": 1600,
            "height": 900,
        }
        return httpx.Response(
            200,
            json={"results": [{**item, "mature": True}, {**item, "id": "ov2"}]},
            request=request,
        )

    result = OpenverseProvider(
        transport=httpx.MockTransport(handler)
    ).search("factory", 3)

    assert [item.id for item in result] == ["ov2"]
    assert result[0].license_status == "RESTRICTED"


def test_wikimedia_maps_imageinfo_metadata():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 7,
                            "title": "File:Factory.jpg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/full.jpg",
                                    "thumburl": "https://upload.wikimedia.org/thumb.jpg",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Factory.jpg",
                                    "width": 2048,
                                    "height": 1365,
                                    "extmetadata": {
                                        "Artist": {"value": "<b>Alice</b>"},
                                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        "LicenseUrl": {
                                            "value": "https://creativecommons.org/licenses/by-sa/4.0/"
                                        },
                                        "Credit": {"value": "Alice / Wikimedia Commons"},
                                    },
                                }
                            ],
                        }
                    ]
                }
            },
            request=request,
        )

    result = WikimediaProvider(
        transport=httpx.MockTransport(handler)
    ).search("factory", 2)

    assert result[0].creator == "Alice"
    assert result[0].license_status == "REUSABLE"
    assert result[0].provider == "wikimedia"


def test_provider_retries_rate_limit_once_then_returns_safe_error():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(429, request=request)

    with pytest.raises(AssetProviderError, match="rate_limit"):
        OpenverseProvider(
            transport=httpx.MockTransport(handler)
        ).search("factory", 1)
    assert calls == 2


class FakeProvider:
    def __init__(self, records):
        self.records = records
        self.calls = 0

    def search(self, query, count):
        self.calls += 1
        return self.records[:count]


def test_fallback_deduplicates_and_only_calls_secondary_when_needed():
    first = OpenverseProvider(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "a",
                            "url": "https://images.example/a.jpg",
                            "thumbnail": "https://images.example/a-t.jpg",
                            "foreign_landing_url": "https://example/a",
                            "license": "cc0",
                            "width": 1000,
                            "height": 800,
                        }
                    ]
                },
                request=request,
            )
        )
    )
    duplicate = first.search("x", 1)[0].model_copy(
        update={"id": "duplicate", "provider": "wikimedia"}
    )
    unique = duplicate.model_copy(
        update={
            "id": "b",
            "original_url": "https://images.example/b.jpg",
            "landing_url": "https://example/b",
        }
    )
    secondary = FakeProvider([duplicate, unique])

    result = FallbackAssetSearch(first, secondary).search("factory", 2)

    assert [item.id for item in result] == ["a", "b"]
    assert secondary.calls == 1


def test_domestic_sogou_provider_accepts_missing_license_and_author():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "data": {
                    "items": [
                        {
                            "picUrl": "https://img.example/full.jpg",
                            "thumbUrl": "https://img.example/thumb.jpg",
                            "pageUrl": "https://cn.example/page",
                            "width": 1600,
                            "height": 900,
                        }
                    ]
                }
            },
            request=request,
        )

    result = JsonImageProvider(
        "sogou",
        "https://pic.sogou.com/napi/pc/searchList",
        transport=httpx.MockTransport(handler),
    ).search("国产大模型", 3)

    assert result[0].provider == "sogou"
    assert result[0].creator is None
    assert result[0].license_status == "UNKNOWN"


def test_provider_chain_uses_chinese_variants_and_continues_failure():
    failing = FakeProvider([])
    working = FakeProvider(
        OpenverseProvider(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"results": []}, request=request
                )
            )
        ).search("x", 1)
    )
    working.records = [
        OpenverseProvider(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "cn",
                                "url": "https://img.example/cn.jpg",
                                "thumbnail": "https://img.example/cn-t.jpg",
                                "foreign_landing_url": "https://cn.example/a",
                                "width": 1600,
                                "height": 900,
                            }
                        ]
                    },
                    request=request,
                )
            )
        ).search("x", 1)[0]
    ]

    result = ProviderChain([failing, working]).search("人工智能", 1)

    assert result[0].id == "cn"
    assert query_variants("人工智能")[1].endswith("横版 高清")
