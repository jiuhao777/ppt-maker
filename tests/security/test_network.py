import pytest

from pptmaker.security.network import is_forbidden_ip


@pytest.mark.parametrize(
    "value",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
    ],
)
def test_blocks_non_public_addresses(value: str):
    assert is_forbidden_ip(value)


@pytest.mark.parametrize("value", ["1.1.1.1", "8.8.8.8", "2606:4700:4700::1111"])
def test_allows_global_addresses(value: str):
    assert not is_forbidden_ip(value)
