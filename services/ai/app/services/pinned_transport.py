import asyncio
import ipaddress
import socket

import httpcore
import httpx

_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_ULA = ipaddress.ip_network("fc00::/7")


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip in _ULA:
        return False
    return ip.is_global


async def _resolve_public_address(host: str, port: int) -> str:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for info in infos:
        candidate = ipaddress.ip_address(info[4][0])
        if _is_public(candidate):
            return str(candidate)
    raise httpcore.ConnectError(f"no public address resolved for {host!r}")


class _PinnedAddressBackend(httpcore.AnyIOBackend):
    # Connects to the address we validated, not the hostname, so a later
    # DNS answer can't redirect an already-approved connection.
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        address = await _resolve_public_address(host, port)
        return await super().connect_tcp(
            address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


def build_public_only_transport() -> httpx.AsyncHTTPTransport:
    # httpx has no public constructor arg for a custom network backend.
    transport = httpx.AsyncHTTPTransport()
    transport._pool._network_backend = _PinnedAddressBackend()
    return transport
