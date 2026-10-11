"""resolve_site_assistant_model: operator-configured provider, fail closed to None."""

from unittest.mock import patch

import pytest
import respx

from app.services.adapters import ollama as ollama_adapter
from app.services.provider import ResolvedModel, resolve_site_assistant_model

_APPROVED = '[{"origin": "http://ollama:11434", "allow_private": true}]'


@pytest.fixture(autouse=True)
def _reset_shared_clients():
    ollama_adapter._http_clients.clear()
    yield
    ollama_adapter._http_clients.clear()


@pytest.fixture
def site_settings():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SITE_ASSISTANT_MODEL = None
        mock_settings.OLLAMA_MODEL = "llama3.2"
        mock_settings.OLLAMA_URL = "http://ollama:11434"
        mock_settings.AI_PROVIDER_APPROVED_ORIGINS = _APPROVED
        yield mock_settings


def test_anthropic_without_platform_key_returns_none(site_settings):
    site_settings.SITE_ASSISTANT_PROVIDER = "anthropic"
    site_settings.ANTHROPIC_API_KEY = None
    assert resolve_site_assistant_model() is None


def test_anthropic_defaults_to_haiku(site_settings):
    site_settings.SITE_ASSISTANT_PROVIDER = "anthropic"
    site_settings.ANTHROPIC_API_KEY = "sk-ant-test"
    resolved = resolve_site_assistant_model()
    assert resolved is not None
    assert resolved.provider_name == "anthropic"
    assert resolved.model_name.startswith("claude-haiku")


def test_anthropic_model_override(site_settings):
    site_settings.SITE_ASSISTANT_PROVIDER = "anthropic"
    site_settings.ANTHROPIC_API_KEY = "sk-ant-test"
    site_settings.SITE_ASSISTANT_MODEL = "claude-sonnet-4-6"
    assert resolve_site_assistant_model().model_name == "claude-sonnet-4-6"


def test_ollama_unapproved_origin_returns_none_without_request(site_settings):
    site_settings.SITE_ASSISTANT_PROVIDER = "ollama"
    site_settings.OLLAMA_URL = "http://evil.example:11434"
    with respx.mock(assert_all_called=False) as router:
        route = router.route()
        assert resolve_site_assistant_model() is None
    assert not route.called


def test_ollama_approved_origin_returns_resolved_model(site_settings):
    site_settings.SITE_ASSISTANT_PROVIDER = "ollama"
    resolved = resolve_site_assistant_model()
    assert isinstance(resolved, ResolvedModel)
    assert resolved.provider_name == "ollama"
    assert resolved.model_name == "llama3.2"


def test_resolved_model_cached_until_config_changes(site_settings):
    site_settings.SITE_ASSISTANT_PROVIDER = "anthropic"
    site_settings.ANTHROPIC_API_KEY = "sk-ant-test"
    first = resolve_site_assistant_model()
    assert resolve_site_assistant_model() is first
    site_settings.SITE_ASSISTANT_MODEL = "claude-sonnet-4-6"
    assert resolve_site_assistant_model() is not first


def test_ollama_without_url_returns_none(site_settings):
    site_settings.SITE_ASSISTANT_PROVIDER = "ollama"
    site_settings.OLLAMA_URL = None
    assert resolve_site_assistant_model() is None
