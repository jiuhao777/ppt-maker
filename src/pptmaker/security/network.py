from ipaddress import ip_address


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
