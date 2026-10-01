import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpcore
import pytest

from app.services.pinned_transport import (
    _PinnedAddressBackend,
    _is_public,
    _resolve_public_address,
    build_public_only_transport,
)


def _addrinfo(ip: str, port: int = 11434):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sockaddr = (ip, port, 0, 0) if family == socket.AF_INET6 else (ip, port)
    return (family, socket.SOCK_STREAM, 6, "", sockaddr)


def _fake_loop(*result_lists):
    loop = MagicMock()
    if len(result_lists) == 1:
        loop.getaddrinfo = AsyncMock(return_value=result_lists[0])
    else:
        loop.getaddrinfo = AsyncMock(side_effect=list(result_lists))
    return loop


class TestIsPublic:
    def test_public_ipv4_is_public(self):
        import ipaddress

        assert _is_public(ipaddress.ip_address("8.8.8.8")) is True

    def test_rfc1918_is_not_public(self):
        import ipaddress

        assert _is_public(ipaddress.ip_address("10.0.0.5")) is False

    def test_link_local_is_not_public(self):
        import ipaddress

        assert _is_public(ipaddress.ip_address("169.254.169.254")) is False

    def test_cgnat_is_not_public(self):
        import ipaddress

        assert _is_public(ipaddress.ip_address("100.64.0.1")) is False

    def test_ula_is_not_public(self):
        import ipaddress

        assert _is_public(ipaddress.ip_address("fd00::1")) is False

    def test_ipv4_mapped_private_is_not_public(self):
        import ipaddress

        assert _is_public(ipaddress.ip_address("::ffff:10.0.0.1")) is False

    def test_ipv4_mapped_public_is_public(self):
        import ipaddress

        assert _is_public(ipaddress.ip_address("::ffff:8.8.8.8")) is True


@pytest.mark.anyio
class TestResolvePublicAddress:
    async def test_rejects_private_only_answer(self):
        with patch("asyncio.get_running_loop", return_value=_fake_loop([_addrinfo("10.0.0.5")])):
            with pytest.raises(httpcore.ConnectError):
                await _resolve_public_address("internal.example", 11434)

    async def test_picks_public_among_mixed_answers(self):
        infos = [_addrinfo("10.0.0.5"), _addrinfo("8.8.8.8")]
        with patch("asyncio.get_running_loop", return_value=_fake_loop(infos)):
            address = await _resolve_public_address("mixed.example", 11434)
        assert address == "8.8.8.8"

    async def test_rebinding_sequence_rejects_second_resolution(self):
        loop = _fake_loop([_addrinfo("8.8.8.8")], [_addrinfo("10.0.0.5")])
        with patch("asyncio.get_running_loop", return_value=loop):
            first = await _resolve_public_address("rebind.example", 11434)
            assert first == "8.8.8.8"
            with pytest.raises(httpcore.ConnectError):
                await _resolve_public_address("rebind.example", 11434)


@pytest.mark.anyio
class TestPinnedAddressBackend:
    async def test_connect_tcp_targets_resolved_address_not_hostname(self):
        backend = _PinnedAddressBackend()
        with (
            patch("asyncio.get_running_loop", return_value=_fake_loop([_addrinfo("8.8.8.8")])),
            patch.object(
                httpcore.AnyIOBackend, "connect_tcp", new=AsyncMock(return_value="stream")
            ) as mock_super,
        ):
            result = await backend.connect_tcp("public.example.com", 443)
        assert result == "stream"
        mock_super.assert_awaited_once_with(
            "8.8.8.8", 443, timeout=None, local_address=None, socket_options=None
        )

    async def test_connect_tcp_raises_when_no_public_address(self):
        backend = _PinnedAddressBackend()
        with patch("asyncio.get_running_loop", return_value=_fake_loop([_addrinfo("10.0.0.5")])):
            with pytest.raises(httpcore.ConnectError):
                await backend.connect_tcp("internal.example", 80)


def test_build_public_only_transport_installs_pinned_backend():
    transport = build_public_only_transport()
    assert isinstance(transport._pool._network_backend, _PinnedAddressBackend)
