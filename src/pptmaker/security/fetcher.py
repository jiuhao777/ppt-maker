from collections.abc import Callable
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urljoin, urlsplit

import httpx

from pptmaker.security.network import is_forbidden_ip


class UnsafeUrl(ValueError):
    pass


@dataclass(frozen=True)
class SafeFetchPolicy:
    allowed_ports: tuple[int, ...] = (80, 443)
    allowed_content_types: tuple[str, ...] = (
        "image/png",
        "image/jpeg",
        "image/webp",
        "application/pdf",
        "application/json",
        "text/html",
        "text/plain",
        "text/csv",
    )
    max_redirects: int = 5
    max_response_bytes: int = 10 * 1024 * 1024
    timeout_seconds: float = 15.0


Resolver = Callable[[str], list[str]]


def validate_target(url: str, resolver: Resolver, policy: SafeFetchPolicy) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrl("only absolute HTTP(S) URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeUrl("URL credentials are forbidden")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrl("port is forbidden") from exc
    if port not in policy.allowed_ports:
        raise UnsafeUrl("port is forbidden")
    try:
        ip_address(parsed.hostname)
        first = second = {parsed.hostname}
    except ValueError:
        try:
            first = set(resolver(parsed.hostname))
            second = set(resolver(parsed.hostname))
        except Exception as exc:
            raise UnsafeUrl("DNS resolution failed") from exc
    if not first or first != second:
        raise UnsafeUrl("DNS answer is empty or unstable")
    try:
        forbidden = any(is_forbidden_ip(address) for address in first)
    except ValueError as exc:
        raise UnsafeUrl("DNS returned an invalid address") from exc
    if forbidden:
        raise UnsafeUrl("target resolves to a forbidden address")


def safe_fetch(
    url: str,
    resolver: Resolver,
    policy: SafeFetchPolicy,
    transport: httpx.BaseTransport | None = None,
) -> bytes:
    timeout = httpx.Timeout(policy.timeout_seconds)
    current = url
    with httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        transport=transport,
    ) as client:
        for redirect_count in range(policy.max_redirects + 1):
            validate_target(current, resolver, policy)
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location or redirect_count == policy.max_redirects:
                        raise UnsafeUrl("redirect limit exceeded")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type not in policy.allowed_content_types:
                    raise UnsafeUrl("response content type is forbidden")
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        declared_length = int(content_length)
                    except ValueError as exc:
                        raise UnsafeUrl("invalid response content length") from exc
                    if declared_length > policy.max_response_bytes:
                        raise UnsafeUrl("response exceeds size limit")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > policy.max_response_bytes:
                        raise UnsafeUrl("response exceeds size limit")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise UnsafeUrl("redirect loop")
