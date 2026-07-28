import html

import httpx

from pptmaker.assets.web_images import (
    BingImageProvider,
    BochaWebImageProvider,
)
from pptmaker.research.contracts import SearchResult
from pptmaker.security.fetcher import SafeFetchResult


class Search:
    def search(self, query, api_key):
        return [
            SearchResult(
                title="国内页面",
                url="https://cn.example/article",
                provider="fake",
            )
        ]


def test_bocha_page_extracts_main_image_without_page_text():
    def fetcher(url, resolver, policy):
        return SafeFetchResult(
            content=(
                b'<html><head><meta property="og:image" '
                b'content="/cover.jpg"></head><body>untrusted</body></html>'
            ),
            content_type="text/html",
            final_url=url,
        )

    result = BochaWebImageProvider(
        "BOCHA_KEY",
        lambda host: ["93.184.216.34"],
        search=Search(),
        fetcher=fetcher,
    ).search("国产大模型", 3)

    assert str(result[0].thumbnail_url) == "https://cn.example/cover.jpg"
    assert result[0].creator is None


def test_bocha_provider_without_key_makes_no_request():
    assert BochaWebImageProvider(
        "",
        lambda host: ["93.184.216.34"],
        search=Search(),
    ).search("主题", 3) == []


def test_bing_cn_maps_embedded_image_metadata():
    metadata = html.escape(
        '{"murl":"https://img.example/full.jpg",'
        '"turl":"https://img.example/thumb.jpg",'
        '"purl":"https://cn.example/page","w":1600,"h":900}',
        quote=True,
    )

    def handler(request):
        return httpx.Response(
            200,
            text=f'<a class="iusc" m="{metadata}"></a>',
            request=request,
        )

    result = BingImageProvider(
        transport=httpx.MockTransport(handler)
    ).search("人工智能", 2)

    assert result[0].provider == "bing-cn"
    assert str(result[0].landing_url) == "https://cn.example/page"
