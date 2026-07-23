import http.client
import socket
import ssl
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from pptmaker.security.network import ValidatedTarget


class PinnedResponse:
    def __init__(
        self,
        connection: http.client.HTTPConnection,
        response: http.client.HTTPResponse,
    ):
        self._connection = connection
        self._response = response
        self.status_code = response.status
        self.headers = {key.lower(): value for key, value in response.getheaders()}

    @property
    def is_redirect(self) -> bool:
        return self.status_code in {301, 302, 303, 307, 308}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise OSError(f"HTTP status {self.status_code}")

    def iter_bytes(self, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        while True:
            chunk = self._response.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def __enter__(self) -> "PinnedResponse":
        return self

    def __exit__(self, *_args) -> None:
        self._response.close()
        self._connection.close()


@dataclass
class PinnedConnector:
    timeout_seconds: float
    ssl_context: ssl.SSLContext | None = None

    def request(
        self,
        target: ValidatedTarget,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
    ) -> PinnedResponse:
        address = target.addresses[0]
        request_headers = dict(headers or {})
        default_port = 443 if target.scheme == "https" else 80
        request_headers["Host"] = (
            target.hostname
            if target.port == default_port
            else f"{target.hostname}:{target.port}"
        )
        if target.scheme == "https":
            context = self.ssl_context or ssl.create_default_context()
            connection = http.client.HTTPSConnection(
                target.hostname,
                target.port,
                timeout=self.timeout_seconds,
                context=context,
            )

            def pinned_create_connection(
                _address,
                timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                source_address=None,
            ):
                return socket.create_connection(
                    (address, target.port),
                    timeout,
                    source_address,
                )

            connection._create_connection = pinned_create_connection
        else:
            connection = http.client.HTTPConnection(
                address,
                target.port,
                timeout=self.timeout_seconds,
            )
        connection.request(method, target.path_and_query, headers=request_headers)
        return PinnedResponse(connection, connection.getresponse())
