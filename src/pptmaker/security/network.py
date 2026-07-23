from dataclasses import dataclass
from ipaddress import ip_address


@dataclass(frozen=True)
class ValidatedTarget:
    scheme: str
    hostname: str
    port: int
    path_and_query: str
    addresses: tuple[str, ...]


def is_forbidden_ip(value: str) -> bool:
    address = ip_address(value)
    if getattr(address, "ipv4_mapped", None) is not None:
        address = address.ipv4_mapped
    return (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
