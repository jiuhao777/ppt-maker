import httpx
import pytest

from pptmaker.security.fetcher import SafeFetchPolicy, UnsafeUrl, safe_fetch, validate_target


PUBLIC_IP = "93.184.216.34"


def public_resolver(_host: str) -> list[str]:
    return [PUBLIC_IP]


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/secret.txt",
        "ftp://example.com/a",
        "http://user:pass@example.com/",
        "http://example.com:22/",
        "http://example.com:70000/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_rejects_unsafe_targets(url: str):
    resolver = lambda host: [host] if host.replace(".", "").isdigit() else [PUBLIC_IP]
    with pytest.raises(UnsafeUrl):
        validate_target(url, resolver, SafeFetchPolicy())


def test_rejects_any_forbidden_dns_answer():
    with pytest.raises(UnsafeUrl, match="forbidden"):
        validate_target(
            "https://example.com/",
            lambda _host: [PUBLIC_IP, "127.0.0.1"],
            SafeFetchPolicy(),
        )


def test_rejects_dns_rebinding_result():
    answers = iter([[PUBLIC_IP], ["127.0.0.1"]])
    with pytest.raises(UnsafeUrl, match="unstable"):
        validate_target(
            "https://example.com/", lambda _host: next(answers), SafeFetchPolicy()
        )


def test_revalidates_redirect_target_and_blocks_metadata():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
            request=request,
        )
    )
    with pytest.raises(UnsafeUrl, match="forbidden"):
        safe_fetch("https://example.com/", public_resolver, SafeFetchPolicy(), transport)


def test_rejects_response_larger_than_limit():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"x" * 11, headers={"Content-Type": "image/png"}, request=request)
    )
    with pytest.raises(UnsafeUrl, match="size limit"):
        safe_fetch(
            "https://example.com/image.png",
            public_resolver,
            SafeFetchPolicy(max_response_bytes=10),
            transport,
        )


def test_rejects_unapproved_response_mime_type():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"binary", headers={"Content-Type": "application/x-msdownload"}, request=request)
    )
    with pytest.raises(UnsafeUrl, match="content type"):
        safe_fetch("https://example.com/file.exe", public_resolver, SafeFetchPolicy(), transport)


def test_rejects_redirect_loop_at_limit():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"Location": "/again"}, request=request)
    )
    with pytest.raises(UnsafeUrl, match="redirect limit"):
        safe_fetch(
            "https://example.com/start",
            public_resolver,
            SafeFetchPolicy(max_redirects=1),
            transport,
        )


def test_fetches_allowed_mime_within_limit():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"png", headers={"Content-Type": "image/png"}, request=request)
    )
    assert safe_fetch(
        "https://example.com/image.png", public_resolver, SafeFetchPolicy(), transport
    ) == b"png"
