"""Site-assistant settings: provider validation and per-provider cap profiles."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_REQUIRED = {"ai_database_url": "postgresql://test:test@localhost/test", "ENCRYPTION_KEY": "k"}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **_REQUIRED, **overrides)  # type: ignore[call-arg]


def test_unknown_provider_fails_startup():
    with pytest.raises(ValidationError, match="SITE_ASSISTANT_PROVIDER"):
        _settings(SITE_ASSISTANT_PROVIDER="openai")


def test_unknown_human_verifier_fails_startup():
    with pytest.raises(ValidationError, match="SITE_ASSISTANT_HUMAN_VERIFIER"):
        _settings(SITE_ASSISTANT_HUMAN_VERIFIER="turnstile")


def test_disabled_by_default():
    assert _settings().SITE_ASSISTANT_ENABLED is False


def test_anthropic_profile_defaults():
    s = _settings(SITE_ASSISTANT_PROVIDER="anthropic")
    assert (s.site_assistant_per_ip_cap, s.site_assistant_global_cap) == (20, 300)


def test_ollama_profile_has_no_global_cap():
    s = _settings(SITE_ASSISTANT_PROVIDER="ollama")
    assert (s.site_assistant_per_ip_cap, s.site_assistant_global_cap) == (200, None)


def test_zero_override_means_unlimited():
    s = _settings(SITE_ASSISTANT_PER_IP_DAILY_CAP=0, SITE_ASSISTANT_GLOBAL_DAILY_CAP=0)
    assert (s.site_assistant_per_ip_cap, s.site_assistant_global_cap) == (None, None)


def test_none_override_uses_profile_default():
    s = _settings(SITE_ASSISTANT_PER_IP_DAILY_CAP=None, SITE_ASSISTANT_GLOBAL_DAILY_CAP=None)
    assert (s.site_assistant_per_ip_cap, s.site_assistant_global_cap) == (20, 300)


def test_blank_env_cap_uses_profile_default(monkeypatch):
    monkeypatch.setenv("SITE_ASSISTANT_PER_IP_DAILY_CAP", "")
    monkeypatch.setenv("SITE_ASSISTANT_GLOBAL_DAILY_CAP", " ")
    s = _settings()
    assert (s.site_assistant_per_ip_cap, s.site_assistant_global_cap) == (20, 300)


def test_positive_override_replaces_profile_default():
    s = _settings(SITE_ASSISTANT_PROVIDER="ollama", SITE_ASSISTANT_GLOBAL_DAILY_CAP=1000)
    assert s.site_assistant_global_cap == 1000


def test_link_hosts_default_to_production_domain():
    assert _settings().site_assistant_link_hosts == {"opengrantflow.com", "www.opengrantflow.com"}


def test_link_hosts_parsed_and_normalised():
    s = _settings(SITE_ASSISTANT_LINK_HOSTS=" LocalHost , opengrantflow.com,")
    assert s.site_assistant_link_hosts == {"localhost", "opengrantflow.com"}


def test_negative_cap_rejected():
    with pytest.raises(ValidationError):
        _settings(SITE_ASSISTANT_PER_IP_DAILY_CAP=-1)
