"""Tests for the Ollama path in resolve_model (replaces OllamaProvider unit tests).

OllamaProvider was removed in Phase 8. Ollama is now wired through
PydanticAI's OpenAIModel with an Ollama-compatible base_url.
"""
import contextlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.services.adapters import ollama as ollama_adapter
from app.services.provider import ResolvedModel, resolve_model

_APPROVED_ORIGINS = '[{"origin": "http://ollama:11434", "allow_private": true}]'


@pytest.fixture(autouse=True)
def _reset_shared_clients():
    ollama_adapter._http_clients.clear()
    yield
    ollama_adapter._http_clients.clear()


def _make_ollama_key(model_name="llama3.2", base_url="http://ollama:11434"):
    user_key = MagicMock()
    user_key.provider.name = "ollama"
    user_key.model_name = model_name
    user_key.encrypted_key = None
    user_key.base_url = base_url
    user_key.customer_id = "cccccccc-0000-0000-0000-000000000003"
    return user_key


class TestResolveModelOllama:
    def test_ollama_key_returns_resolved_model(self):
        user_key = _make_ollama_key()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_PROVIDER_APPROVED_ORIGINS = _APPROVED_ORIGINS
            resolved = resolve_model(user_key=user_key)
        assert isinstance(resolved, ResolvedModel)
        assert resolved.provider_name == "ollama"
        assert resolved.model_name == "llama3.2"

    def test_ollama_reuses_one_http_client_per_egress_mode(self):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_PROVIDER_APPROVED_ORIGINS = _APPROVED_ORIGINS
            first = resolve_model(user_key=_make_ollama_key())
            second = resolve_model(user_key=_make_ollama_key())
        assert first.model.client._client is second.model.client._client

    def test_ollama_uses_base_url_from_key(self):
        user_key = _make_ollama_key(base_url="http://custom-ollama:11434")
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_PROVIDER_APPROVED_ORIGINS = (
                '[{"origin": "http://custom-ollama:11434", "allow_private": true}]'
            )
            resolved = resolve_model(user_key=user_key)
        assert resolved is not None

    def test_ollama_falls_back_to_settings_url_when_no_base_url(self):
        user_key = _make_ollama_key()
        user_key.base_url = None
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.OLLAMA_URL = "http://settings-ollama:11434"
            mock_settings.ENCRYPTION_KEY = "key"
            mock_settings.AI_PROVIDER_APPROVED_ORIGINS = (
                '[{"origin": "http://settings-ollama:11434", "allow_private": true}]'
            )
            resolved = resolve_model(user_key=user_key)
        assert resolved is not None
        assert resolved.provider_name == "ollama"

    def test_ollama_returns_none_when_no_url_available(self):
        user_key = _make_ollama_key()
        user_key.base_url = None
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.OLLAMA_URL = None
            mock_settings.ENCRYPTION_KEY = "key"
            resolved = resolve_model(user_key=user_key)
        assert resolved is None

    def test_stored_unapproved_origin_resolves_to_no_provider(self):
        """A row saved before this policy existed, or whose approval was later
        revoked, must fail closed rather than reach the stored host."""
        user_key = _make_ollama_key(base_url="http://users:8000")
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_PROVIDER_APPROVED_ORIGINS = _APPROVED_ORIGINS
            resolved = resolve_model(user_key=user_key)
        assert resolved is None

    def test_client_does_not_follow_redirects(self):
        user_key = _make_ollama_key()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_PROVIDER_APPROVED_ORIGINS = _APPROVED_ORIGINS
            resolved = resolve_model(user_key=user_key)
        http_client = resolved.model.client._client
        assert isinstance(http_client, httpx.AsyncClient)
        assert http_client.follow_redirects is False


@pytest.mark.anyio
class TestOllamaRedirectNotFollowed:
    async def test_redirect_to_internal_address_is_not_followed(self):
        user_key = _make_ollama_key()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_PROVIDER_APPROVED_ORIGINS = _APPROVED_ORIGINS
            resolved = resolve_model(user_key=user_key)
        http_client = resolved.model.client._client

        with respx.mock(assert_all_called=False) as mock:
            origin_route = mock.get("http://ollama:11434/probe").mock(
                return_value=httpx.Response(
                    302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
                )
            )
            internal_route = mock.get("http://169.254.169.254/latest/meta-data/").mock(
                return_value=httpx.Response(200, text="should never be reached")
            )
            response = await http_client.get("http://ollama:11434/probe")

        assert response.status_code == 302
        assert origin_route.called
        assert not internal_route.called


class _StubHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def _local_stub_server():
    server = HTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join()


@pytest.mark.anyio
class TestOllamaPrivateAllowedOrigin:
    async def test_private_allowed_origin_reaches_local_stub_server(self):
        """allow_private origins skip address pinning, so a loopback stub
        (normally rejected as non-public) is reachable when approved."""
        with _local_stub_server() as port:
            base_url = f"http://127.0.0.1:{port}"
            user_key = _make_ollama_key(base_url=base_url)
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.AI_PROVIDER_APPROVED_ORIGINS = (
                    f'[{{"origin": "{base_url}", "allow_private": true}}]'
                )
                resolved = resolve_model(user_key=user_key)
            http_client = resolved.model.client._client
            response = await http_client.get(f"{base_url}/health")
        assert response.status_code == 200

    async def test_public_only_origin_rejects_the_same_loopback_stub(self):
        with _local_stub_server() as port:
            base_url = f"http://127.0.0.1:{port}"
            user_key = _make_ollama_key(base_url=base_url)
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.AI_PROVIDER_APPROVED_ORIGINS = (
                    f'[{{"origin": "{base_url}", "allow_private": false}}]'
                )
                resolved = resolve_model(user_key=user_key)
            http_client = resolved.model.client._client
            with pytest.raises(httpx.ConnectError):
                await http_client.get(f"{base_url}/health")
