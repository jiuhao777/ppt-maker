from unittest.mock import Mock, patch

from pptmaker.security.fetcher import SafeFetchPolicy, safe_fetch, validate_target
from pptmaker.security.network import ValidatedTarget
from pptmaker.security.pinned_http import PinnedConnector


PUBLIC_IP = "93.184.216.34"


class FakeResponse:
    status_code = 200
    is_redirect = False
    headers = {"content-type": "image/png"}

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield b"png"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class RecordingConnector:
    def __init__(self):
        self.targets = []

    def request(self, target, method="GET", headers=None):
        self.targets.append(target)
        return FakeResponse()


def test_validation_returns_stable_public_addresses():
    target = validate_target(
        "https://example.com/a?q=1",
        lambda _host: [PUBLIC_IP],
        SafeFetchPolicy(),
    )
    assert target.hostname == "example.com"
    assert target.addresses == (PUBLIC_IP,)
    assert target.path_and_query == "/a?q=1"


def test_safe_fetch_passes_only_validated_ip_to_connector():
    connector = RecordingConnector()
    calls = []

    def resolver(_host):
        calls.append(True)
        return [PUBLIC_IP] if len(calls) <= 2 else ["127.0.0.1"]

    assert safe_fetch(
        "https://example.com/a.png",
        resolver,
        SafeFetchPolicy(),
        connector=connector,
    ) == b"png"
    assert connector.targets[0].addresses == (PUBLIC_IP,)
    assert len(calls) == 2


def test_https_connector_uses_pinned_ip_and_original_sni():
    target = ValidatedTarget(
        scheme="https",
        hostname="example.com",
        port=443,
        path_and_query="/asset",
        addresses=(PUBLIC_IP,),
    )
    raw_socket = Mock()
    wrapped_socket = Mock()
    response = Mock()
    response.status = 200
    response.getheaders.return_value = [("Content-Type", "image/png")]
    context = Mock()
    context.wrap_socket.return_value = wrapped_socket

    with patch("socket.create_connection", return_value=raw_socket) as connect:
        connector = PinnedConnector(5, ssl_context=context)
        with patch("http.client.HTTPSConnection.getresponse", return_value=response):
            pinned = connector.request(target)

    connect.assert_called_once()
    assert connect.call_args.args[0] == (PUBLIC_IP, 443)
    context.wrap_socket.assert_called_once_with(
        raw_socket, server_hostname="example.com"
    )
    assert pinned.status_code == 200
