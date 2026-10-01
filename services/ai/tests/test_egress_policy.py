import pytest

from app.services.egress_policy import (
    ApprovedOrigin,
    is_approved,
    normalize_origin,
    parse_approved_origins,
)


class TestNormalizeOrigin:
    def test_lowercases_scheme_and_host(self):
        assert normalize_origin("HTTP://Ollama:11434") == "http://ollama:11434"

    def test_strips_default_http_port(self):
        assert normalize_origin("http://ollama:80") == "http://ollama"

    def test_strips_default_https_port(self):
        assert normalize_origin("https://ollama:443") == "https://ollama"

    def test_keeps_non_default_port(self):
        assert normalize_origin("http://ollama:11434") == "http://ollama:11434"

    def test_ignores_path_and_trailing_slash(self):
        assert normalize_origin("http://ollama:11434/v1/chat/") == "http://ollama:11434"

    def test_rejects_userinfo(self):
        assert normalize_origin("http://user:pass@ollama:11434") is None

    def test_rejects_file_scheme(self):
        assert normalize_origin("file:///etc/passwd") is None

    def test_rejects_gopher_scheme(self):
        assert normalize_origin("gopher://ollama:11434") is None

    def test_rejects_url_with_no_host(self):
        assert normalize_origin("http://") is None

    @pytest.mark.parametrize("url", [
        "http://[::1", "http://ollama:bad", "http://ollama:65536",
    ])
    def test_rejects_malformed_url(self, url):
        assert normalize_origin(url) is None
        assert is_approved(url, []) is None

    @pytest.mark.parametrize("url, expected", [
        ("http://[::1]:11434", "http://[::1]:11434"),
        ("http://[::1]:80", "http://[::1]"),
        ("https://[2001:DB8::1]:443/path", "https://[2001:db8::1]"),
    ])
    def test_ipv6_endpoint_roundtrip(self, url, expected):
        approved = parse_approved_origins(
            '[{"origin": "' + url + '", "allow_private": true}]'
        )
        assert approved[0].origin == expected
        assert normalize_origin(expected) == expected
        assert is_approved(expected, approved) == approved[0]


class TestParseApprovedOrigins:
    def test_none_returns_empty_list(self):
        assert parse_approved_origins(None) == []

    def test_empty_string_returns_empty_list(self):
        assert parse_approved_origins("") == []

    def test_parses_origin_and_allow_private(self):
        raw = '[{"origin": "http://ollama:11434", "allow_private": true}]'
        assert parse_approved_origins(raw) == [
            ApprovedOrigin(origin="http://ollama:11434", allow_private=True)
        ]

    def test_defaults_allow_private_to_false(self):
        raw = '[{"origin": "https://api.example.com"}]'
        assert parse_approved_origins(raw) == [
            ApprovedOrigin(origin="https://api.example.com", allow_private=False)
        ]

    def test_parses_optional_label(self):
        raw = '[{"origin": "http://ollama:11434", "allow_private": true, "label": "Local Ollama"}]'
        assert parse_approved_origins(raw)[0].label == "Local Ollama"

    def test_label_defaults_to_none(self):
        raw = '[{"origin": "http://ollama:11434", "allow_private": true}]'
        assert parse_approved_origins(raw)[0].label is None

    def test_normalizes_entries(self):
        raw = '[{"origin": "HTTP://Ollama:80", "allow_private": true}]'
        assert parse_approved_origins(raw)[0].origin == "http://ollama"

    def test_rejects_invalid_origin(self):
        with pytest.raises(ValueError):
            parse_approved_origins('[{"origin": "file:///etc/passwd"}]')

    @pytest.mark.parametrize(
        "raw", ["not json", '{"origin": "http://ollama"}', '["http://ollama"]', '[{"label": "x"}]']
    )
    def test_malformed_config_raises_value_error(self, raw):
        with pytest.raises(ValueError):
            parse_approved_origins(raw)

    def test_settings_reject_malformed_config_at_load(self, monkeypatch):
        from pydantic import ValidationError

        from app.core.config import Settings

        monkeypatch.setenv("AI_PROVIDER_APPROVED_ORIGINS", '[{"label": "no origin"}]')
        with pytest.raises(ValidationError):
            Settings()


class TestIsApproved:
    def _approved(self):
        return [
            ApprovedOrigin(origin="http://ollama:11434", allow_private=True),
            ApprovedOrigin(origin="https://api.example.com", allow_private=False),
        ]

    def test_matches_normalized_origin(self):
        result = is_approved("HTTP://Ollama:11434/v1/", self._approved())
        assert result == ApprovedOrigin(origin="http://ollama:11434", allow_private=True)

    def test_no_match_returns_none(self):
        assert is_approved("http://users:8000", self._approved()) is None

    def test_disallowed_scheme_returns_none(self):
        assert is_approved("file:///etc/passwd", self._approved()) is None
