from unittest.mock import ANY, AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from app.api.settings_routes import get_db, get_validated_user
from tests.factories.user import ValidUserFactory

client = TestClient(app)

_ENCRYPTED_KEY = "dGVzdC1lbmNyeXB0ZWQ="  # fake base64 blob

_LIST_FOR_CUSTOMER = "app.api.settings_routes.list_for_customer"
_GET_CUSTOMER_AI_DEFAULTS = "app.api.settings_routes.get_customer_ai_defaults"
_GET_BY_NAME = "app.api.settings_routes.get_by_name"
_MODEL_EXISTS = "app.api.settings_routes.model_exists_for_provider"
_VALIDATE = "app.api.settings_routes._validate_key_with_provider"
_ENCRYPT = "app.api.settings_routes.encrypt"
_DECRYPT = "app.api.settings_routes.decrypt"
_CREATE = "app.api.settings_routes.create"
_SET_DEFAULT = "app.api.settings_routes.set_default"
_DELETE = "app.api.settings_routes.delete"
_SET_PLATFORM_FALLBACK = "app.api.settings_routes.set_platform_fallback"


def _make_admin_user():
    return ValidUserFactory(role="superuser")


def _make_regular_user():
    return ValidUserFactory(role="user")


def _make_provider(name="anthropic", has_key_prefix=True):
    p = MagicMock()
    p.id = "bbbbbbbb-0000-0000-0000-000000000002"
    p.name = name
    p.display_name = "Anthropic" if name == "anthropic" else "Ollama (Local)"
    p.key_prefix = "sk-ant-" if has_key_prefix else None
    p.is_active = True
    return p


def _make_config(config_id="id-1", provider_name="anthropic", is_default=False, has_key=True):
    row = MagicMock()
    row.id = config_id
    row.provider.name = provider_name
    row.label = "My key"
    row.model_name = "claude-sonnet-4-6"
    row.encrypted_key = _ENCRYPTED_KEY if has_key else None
    row.base_url = None
    row.is_default = is_default
    return row


def _mock_db():
    async def _override():
        yield AsyncMock()

    return _override


class TestGetAiSettings:
    def setup_method(self):
        app.dependency_overrides[get_validated_user] = _make_admin_user
        app.dependency_overrides[get_db] = _mock_db()

    def teardown_method(self):
        app.dependency_overrides.pop(get_validated_user, None)
        app.dependency_overrides.pop(get_db, None)

    def test_returns_all_configs_with_is_default_flag(self):
        configs = [_make_config("id-1", is_default=True), _make_config("id-2", is_default=False)]
        with (
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=configs)),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch(_DECRYPT, return_value="sk-ant-api03-secretvalue"),
        ):
            response = client.get("/api/v1/ai/settings")
        assert response.status_code == 200
        data = response.json()
        assert len(data["configs"]) == 2
        assert data["configs"][0]["is_default"] is True
        assert data["configs"][1]["is_default"] is False
        assert data["platform_fallback_enabled"] is False

    def test_masked_key_never_exposes_raw_key(self):
        with (
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[_make_config()])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch(_DECRYPT, return_value="sk-ant-api03-secretvalue"),
        ):
            response = client.get("/api/v1/ai/settings")
        masked = response.json()["configs"][0]["masked_key"]
        assert masked is not None
        assert "secretvalue" not in masked

    def test_includes_platform_fallback_enabled_flag(self):
        defaults = MagicMock(platform_fallback_enabled=True)
        with (
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=defaults)),
        ):
            response = client.get("/api/v1/ai/settings")
        assert response.json()["platform_fallback_enabled"] is True

    def test_user_role_forbidden(self):
        app.dependency_overrides[get_validated_user] = _make_regular_user
        response = client.get("/api/v1/ai/settings")
        assert response.status_code == 403

    def test_exposes_approved_endpoints_with_label_fallback(self):
        with (
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch(
                "app.api.settings_routes.settings.AI_PROVIDER_APPROVED_ORIGINS",
                '[{"origin": "http://ollama:11434", "allow_private": true, "label": "Local"},'
                ' {"origin": "http://host.docker.internal:11434", "allow_private": true}]',
            ),
        ):
            response = client.get("/api/v1/ai/settings")
        endpoints = response.json()["approved_endpoints"]
        assert endpoints == [
            {"origin": "http://ollama:11434", "label": "Local"},
            {
                "origin": "http://host.docker.internal:11434",
                "label": "http://host.docker.internal:11434",
            },
        ]

    def test_no_approved_origins_returns_empty_endpoints(self):
        with (
            patch("app.api.settings_routes.settings.AI_PROVIDER_APPROVED_ORIGINS", None),
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
        ):
            response = client.get("/api/v1/ai/settings")
        assert response.json()["approved_endpoints"] == []


class TestCreateAiKey:
    def setup_method(self):
        app.dependency_overrides[get_validated_user] = _make_admin_user
        app.dependency_overrides[get_db] = _mock_db()

    def teardown_method(self):
        app.dependency_overrides.pop(get_validated_user, None)
        app.dependency_overrides.pop(get_db, None)

    def test_second_config_for_same_provider_succeeds(self):
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=_make_provider())),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
            patch(_VALIDATE, new=AsyncMock()),
            patch(_ENCRYPT, return_value=_ENCRYPTED_KEY),
            patch(_CREATE, new=AsyncMock()) as mock_create,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[_make_config()])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch(_DECRYPT, return_value="sk-ant-api03-x"),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={
                    "provider": "anthropic",
                    "label": "Fast tasks",
                    "key": "sk-ant-api03-x",
                    "model": "claude-haiku-4-5",
                },
            )
        assert response.status_code == 200
        mock_create.assert_awaited_once()

    def test_ollama_key_without_base_url_defaults_to_configured_default(self):
        ollama_provider = _make_provider("ollama", has_key_prefix=False)
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=ollama_provider)),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
            patch(_VALIDATE, new=AsyncMock()),
            patch(_CREATE, new=AsyncMock()) as mock_create,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch("app.api.settings_routes.settings.OLLAMA_URL", "http://ollama:11434"),
            patch(
                "app.api.settings_routes.settings.AI_PROVIDER_APPROVED_ORIGINS",
                '[{"origin": "http://ollama:11434", "allow_private": true}]',
            ),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={"provider": "ollama", "model": "llama3.2"},
            )
        assert response.status_code == 200
        assert mock_create.await_args.kwargs["base_url"] == "http://ollama:11434"

    def test_ollama_key_with_unapproved_base_url_rejected(self):
        ollama_provider = _make_provider("ollama", has_key_prefix=False)
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=ollama_provider)),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
            patch(
                "app.api.settings_routes.settings.AI_PROVIDER_APPROVED_ORIGINS",
                '[{"origin": "http://ollama:11434", "allow_private": true}]',
            ),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={"provider": "ollama", "model": "llama3.2", "base_url": "http://users:8000"},
            )
        assert response.status_code == 422

    def test_ollama_key_with_metadata_endpoint_rejected(self):
        ollama_provider = _make_provider("ollama", has_key_prefix=False)
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=ollama_provider)),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
            patch(
                "app.api.settings_routes.settings.AI_PROVIDER_APPROVED_ORIGINS",
                '[{"origin": "http://ollama:11434", "allow_private": true}]',
            ),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={
                    "provider": "ollama",
                    "model": "llama3.2",
                    "base_url": "http://169.254.169.254",
                },
            )
        assert response.status_code == 422

    def test_ollama_key_with_approved_base_url_succeeds(self):
        ollama_provider = _make_provider("ollama", has_key_prefix=False)
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=ollama_provider)),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
            patch(_VALIDATE, new=AsyncMock()),
            patch(_CREATE, new=AsyncMock()) as mock_create,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch(
                "app.api.settings_routes.settings.AI_PROVIDER_APPROVED_ORIGINS",
                '[{"origin": "http://ollama:11434", "allow_private": true}]',
            ),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={
                    "provider": "ollama",
                    "model": "llama3.2",
                    "base_url": "http://ollama:11434",
                },
            )
        assert response.status_code == 200
        assert mock_create.await_args.kwargs["base_url"] == "http://ollama:11434"

    def test_base_url_rejected_for_key_requiring_provider(self):
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=_make_provider())),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={
                    "provider": "anthropic",
                    "key": "sk-ant-api03-x",
                    "model": "claude-sonnet-4-6",
                    "base_url": "http://ollama:11434",
                },
            )
        assert response.status_code == 422

    def test_unknown_provider_returns_404(self):
        with patch(_GET_BY_NAME, new=AsyncMock(return_value=None)):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={"provider": "unknown", "key": "any", "model": "claude-sonnet-4-6"},
            )
        assert response.status_code == 404

    def test_invalid_key_format_rejected(self):
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=_make_provider())),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={
                    "provider": "anthropic",
                    "key": "not-a-valid-key",
                    "model": "claude-sonnet-4-6",
                },
            )
        assert response.status_code == 422

    def test_unsupported_model_rejected(self):
        """A model must belong to the given provider (e.g. claude-haiku-4-5
        is not valid for ollama) — see app/crud/ai_provider_model.py."""
        ollama_provider = _make_provider("ollama", has_key_prefix=False)
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=ollama_provider)),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=False)),
        ):
            response = client.post(
                "/api/v1/ai/settings/keys",
                json={"provider": "ollama", "model": "claude-haiku-4-5"},
            )
        assert response.status_code == 422

    def test_user_role_forbidden(self):
        app.dependency_overrides[get_validated_user] = _make_regular_user
        response = client.post(
            "/api/v1/ai/settings/keys",
            json={"provider": "anthropic", "key": "sk-ant-api03-x", "model": "claude-sonnet-4-6"},
        )
        assert response.status_code == 403


class TestSetDefaultAiKey:
    def setup_method(self):
        app.dependency_overrides[get_validated_user] = _make_admin_user
        app.dependency_overrides[get_db] = _mock_db()

    def teardown_method(self):
        app.dependency_overrides.pop(get_validated_user, None)
        app.dependency_overrides.pop(get_db, None)

    def test_sets_a_non_default_config_as_default(self):
        with (
            patch(_SET_DEFAULT, new=AsyncMock()) as mock_set_default,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[_make_config(is_default=True)])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch(_DECRYPT, return_value="sk-ant-api03-x"),
        ):
            response = client.post("/api/v1/ai/settings/keys/id-2/default")
        assert response.status_code == 200
        mock_set_default.assert_awaited_once()

    def test_unknown_config_returns_404(self):
        with patch(_SET_DEFAULT, new=AsyncMock(side_effect=ValueError("not found"))):
            response = client.post("/api/v1/ai/settings/keys/missing/default")
        assert response.status_code == 404

    def test_user_role_forbidden(self):
        app.dependency_overrides[get_validated_user] = _make_regular_user
        response = client.post("/api/v1/ai/settings/keys/id-2/default")
        assert response.status_code == 403


class TestDeleteAiKey:
    def setup_method(self):
        app.dependency_overrides[get_validated_user] = _make_admin_user
        app.dependency_overrides[get_db] = _mock_db()

    def teardown_method(self):
        app.dependency_overrides.pop(get_validated_user, None)
        app.dependency_overrides.pop(get_db, None)

    def test_deletes_a_non_default_config(self):
        with (
            patch(_DELETE, new=AsyncMock()) as mock_delete,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
        ):
            response = client.request("DELETE", "/api/v1/ai/settings/keys/id-1")
        assert response.status_code == 200
        mock_delete.assert_awaited_once()

    def test_delete_default_without_replacement_succeeds(self):
        """An AI config is never required to use the app, so deleting the
        default with no replacement named is allowed, not a 409."""
        with (
            patch(_DELETE, new=AsyncMock()) as mock_delete,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
        ):
            response = client.request("DELETE", "/api/v1/ai/settings/keys/id-1")
        assert response.status_code == 200
        mock_delete.assert_awaited_once_with(ANY, "id-1", ANY, new_default_id=None)

    def test_delete_default_with_replacement_succeeds(self):
        with (
            patch(_DELETE, new=AsyncMock()) as mock_delete,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[_make_config(is_default=True)])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            patch(_DECRYPT, return_value="sk-ant-api03-x"),
        ):
            response = client.request(
                "DELETE", "/api/v1/ai/settings/keys/id-1", json={"new_default_id": "id-2"}
            )
        assert response.status_code == 200
        mock_delete.assert_awaited_once_with(ANY, "id-1", ANY, new_default_id="id-2")

    def test_unknown_replacement_returns_404(self):
        with patch(_DELETE, new=AsyncMock(side_effect=ValueError("not found"))):
            response = client.request(
                "DELETE", "/api/v1/ai/settings/keys/id-1", json={"new_default_id": "missing"}
            )
        assert response.status_code == 404

    def test_user_role_forbidden(self):
        app.dependency_overrides[get_validated_user] = _make_regular_user
        response = client.request("DELETE", "/api/v1/ai/settings/keys/id-1")
        assert response.status_code == 403


class TestSetPlatformFallbackRoute:
    def setup_method(self):
        app.dependency_overrides[get_db] = _mock_db()

    def teardown_method(self):
        app.dependency_overrides.pop(get_validated_user, None)
        app.dependency_overrides.pop(get_db, None)

    def test_admin_gets_403(self):
        app.dependency_overrides[get_validated_user] = lambda: ValidUserFactory(role="admin")
        response = client.put("/api/v1/ai/settings/platform-fallback", json={"enabled": True})
        assert response.status_code == 403

    def test_superuser_succeeds(self):
        app.dependency_overrides[get_validated_user] = lambda: ValidUserFactory(role="superuser")
        with (
            patch(_SET_PLATFORM_FALLBACK, new=AsyncMock()) as mock_set,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
        ):
            response = client.put("/api/v1/ai/settings/platform-fallback", json={"enabled": True})
        assert response.status_code == 200
        mock_set.assert_awaited_once_with(ANY, True, ANY)


class TestCustomerScopedLookup:
    """Admins of the same customer share the same set of configs and default."""

    CUSTOMER_ID = "cccccccc-0000-0000-0000-000000000003"

    def setup_method(self):
        app.dependency_overrides[get_db] = _mock_db()

    def teardown_method(self):
        app.dependency_overrides.pop(get_validated_user, None)
        app.dependency_overrides.pop(get_db, None)

    def _admin(self, user_id):
        return ValidUserFactory(role="admin", user_id=user_id, customer_id=self.CUSTOMER_ID)

    def test_get_settings_keyed_by_customer_id_regardless_of_which_admin(self):
        for admin in (self._admin("admin-a"), self._admin("admin-b")):
            app.dependency_overrides[get_validated_user] = lambda admin=admin: admin
            with (
                patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])) as mock_list,
                patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
            ):
                client.get("/api/v1/ai/settings")
            mock_list.assert_awaited_once_with(self.CUSTOMER_ID, ANY)

    def test_create_scopes_new_config_by_customer_id_not_user_id(self):
        app.dependency_overrides[get_validated_user] = lambda: self._admin("admin-b")
        with (
            patch(_GET_BY_NAME, new=AsyncMock(return_value=_make_provider())),
            patch(_MODEL_EXISTS, new=AsyncMock(return_value=True)),
            patch(_VALIDATE, new=AsyncMock()),
            patch(_ENCRYPT, return_value=_ENCRYPTED_KEY),
            patch(_CREATE, new=AsyncMock()) as mock_create,
            patch(_LIST_FOR_CUSTOMER, new=AsyncMock(return_value=[])),
            patch(_GET_CUSTOMER_AI_DEFAULTS, new=AsyncMock(return_value=None)),
        ):
            client.post(
                "/api/v1/ai/settings/keys",
                json={
                    "provider": "anthropic",
                    "key": "sk-ant-api03-x",
                    "model": "claude-sonnet-4-6",
                },
            )
        assert mock_create.await_args is not None
        assert mock_create.await_args.kwargs["customer_id"] == self.CUSTOMER_ID
