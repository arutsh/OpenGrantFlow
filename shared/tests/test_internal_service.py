import uuid

import fakeredis
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from shared.security import session_revocation
from shared.security.current_user_context import get_current_user_id
from shared.security.internal_service import (
    INTERNAL_SERVICE_HEADER,
    _valid_internal_service_token,
    get_validated_user_or_internal_service,
    require_internal_service,
)
from shared.security.jwt_utils import create_access_token

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def token_set(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "correct-secret")


class TestValidInternalServiceToken:
    def test_valid_token_matches(self):
        assert _valid_internal_service_token("correct-secret") is True

    def test_wrong_token_rejected(self):
        assert _valid_internal_service_token("wrong-secret") is False

    def test_missing_token_rejected(self):
        assert _valid_internal_service_token(None) is False

    def test_unset_setting_rejects_even_a_matching_empty_token(self, monkeypatch):
        monkeypatch.delenv("INTERNAL_SERVICE_TOKEN", raising=False)
        assert _valid_internal_service_token("") is False
        assert _valid_internal_service_token("correct-secret") is False


class TestRequireInternalService:
    async def test_valid_token_passes(self):
        await require_internal_service(x_internal_service_token="correct-secret")

    async def test_wrong_token_is_401(self):
        with pytest.raises(HTTPException) as exc_info:
            await require_internal_service(x_internal_service_token="wrong-secret")
        assert exc_info.value.status_code == 401

    async def test_missing_token_is_401(self):
        with pytest.raises(HTTPException) as exc_info:
            await require_internal_service(x_internal_service_token=None)
        assert exc_info.value.status_code == 401

    async def test_unset_setting_is_401_even_with_no_header_sent(self, monkeypatch):
        monkeypatch.delenv("INTERNAL_SERVICE_TOKEN", raising=False)
        with pytest.raises(HTTPException) as exc_info:
            await require_internal_service(x_internal_service_token=None)
        assert exc_info.value.status_code == 401


class TestValidatedUserOrInternalServiceContext:
    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setattr(session_revocation, "_redis_client", fakeredis.FakeStrictRedis())
        app = FastAPI()

        @app.get("/whoami")
        async def whoami(caller: dict | None = Depends(get_validated_user_or_internal_service)):
            current = get_current_user_id()
            current_str = str(current) if current else None
            return {"is_service": caller is None, "current_user_id": current_str}

        return TestClient(app)

    def test_user_token_keeps_current_user_id_set_inside_endpoint(self, client):
        user_id = str(uuid.uuid4())
        token = create_access_token(
            {"user_id": user_id, "session_id": "s", "role": "user", "email_verified": True}
        )
        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == {"is_service": False, "current_user_id": user_id}

    def test_service_token_yields_none_and_no_current_user(self, client):
        response = client.get("/whoami", headers={INTERNAL_SERVICE_HEADER: "correct-secret"})
        assert response.status_code == 200
        assert response.json() == {"is_service": True, "current_user_id": None}
