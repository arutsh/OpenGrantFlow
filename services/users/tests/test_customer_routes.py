"""Route tests for /api/customers/ covering the auth + search-filter changes
made alongside ticket #191 (customer discovery filters, auth hardening).
"""

from uuid import uuid4

import pytest

from shared.security.internal_service import INTERNAL_SERVICE_HEADER
from shared.security.jwt_utils import create_access_token
from tests.factories.user import CustomerFactory


async def _persist(db, obj):
    db.add(obj)
    await db.commit()
    return obj


def _strip_auth_overrides(client):
    # get_validated_user_or_internal_service calls get_current_user/get_validated_user
    # directly, not through FastAPI's DI, so make_client's overrides don't reach it.
    app = client.app
    from app.utils.security import get_current_user
    from shared.security.dependencies import get_validated_user
    from shared.security.internal_service import get_validated_user_or_internal_service

    for dep in (get_current_user, get_validated_user, get_validated_user_or_internal_service):
        app.dependency_overrides.pop(dep, None)


def _bearer(user_id):
    claims = {"user_id": str(user_id), "role": "user", "email_verified": True}
    return {"Authorization": f"Bearer {create_access_token(claims)}"}


@pytest.mark.anyio
class TestListCustomers:
    async def test_requires_auth(self, make_client, db):
        client = make_client(db=db)
        app = client.app
        from app.utils.security import get_current_user
        from shared.security.dependencies import get_validated_user

        # get_validated_user's real implementation still delegates to
        # get_current_user for the actual decode, so both overrides need to
        # come off to exercise the unauthenticated path.
        del app.dependency_overrides[get_current_user]
        del app.dependency_overrides[get_validated_user]

        response = client.get("/api/customers/")

        assert response.status_code == 401

    async def test_search_escapes_ilike_wildcards(self, make_client, db):
        await _persist(db, CustomerFactory.build(name="100% Match Org"))
        await _persist(db, CustomerFactory.build(name="Unrelated Org"))
        client = make_client(db=db)

        response = client.get("/api/customers/", params={"search": "100%"})

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["name"] == "100% Match Org"

    async def test_search_underscore_is_literal(self, make_client, db):
        await _persist(db, CustomerFactory.build(name="a_b Org"))
        await _persist(db, CustomerFactory.build(name="axb Org"))
        client = make_client(db=db)

        response = client.get("/api/customers/", params={"search": "a_b"})

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["name"] == "a_b Org"

    async def test_is_ngo_filter(self, make_client, db):
        await _persist(db, CustomerFactory.build(name="NGO Org", is_ngo=True))
        await _persist(db, CustomerFactory.build(name="Donor Org", is_ngo=False))
        client = make_client(db=db)

        response = client.get("/api/customers/", params={"is_ngo": True})

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["name"] == "NGO Org"


@pytest.mark.anyio
class TestCreateCustomer:
    async def test_requires_auth(self, make_client, db):
        client = make_client(db=db)
        app = client.app
        from app.utils.security import get_current_user
        from shared.security.dependencies import get_validated_user

        # get_validated_user's real implementation still delegates to
        # get_current_user for the actual decode, so both overrides need to
        # come off to exercise the unauthenticated path.
        del app.dependency_overrides[get_current_user]
        del app.dependency_overrides[get_validated_user]

        response = client.post(
            "/api/customers/",
            json={"name": "New Org", "country": "GB", "currency": "GBP"},
        )

        assert response.status_code == 401

    async def test_respects_explicit_is_ngo_false(self, make_client, db):
        client = make_client(db=db)

        response = client.post(
            "/api/customers/",
            json={
                "name": "Donor Org",
                "country": "GB",
                "currency": "GBP",
                "is_ngo": False,
            },
        )

        assert response.status_code == 200
        assert response.json()["is_ngo"] is False


@pytest.mark.anyio
class TestGetCustomer:
    async def test_requires_auth(self, make_client, db):
        customer = await _persist(db, CustomerFactory.build())
        client = make_client(db=db)
        app = client.app
        from app.utils.security import get_current_user
        from shared.security.dependencies import get_validated_user

        # get_validated_user's real implementation still delegates to
        # get_current_user for the actual decode, so both overrides need to
        # come off to exercise the unauthenticated path.
        del app.dependency_overrides[get_current_user]
        del app.dependency_overrides[get_validated_user]

        response = client.get(f"/api/customers/{customer.id}")

        assert response.status_code == 401


@pytest.mark.anyio
class TestGetCustomersByIds:
    async def test_empty_list_returns_empty(self, make_client, db, monkeypatch):
        monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "shared-secret")
        await _persist(db, CustomerFactory.build())
        client = make_client(db=db)

        response = client.post(
            "/api/customers/by_ids/",
            json=[],
            headers={INTERNAL_SERVICE_HEADER: "shared-secret"},
        )

        assert response.status_code == 200
        assert response.json() == []

    async def test_anonymous_is_401(self, make_client, db, monkeypatch):
        monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "shared-secret")
        client = make_client(db=db)
        _strip_auth_overrides(client)

        response = client.post("/api/customers/by_ids/", json=[])

        assert response.status_code == 401

    async def test_wrong_internal_service_token_falls_through_to_401(
        self, make_client, db, monkeypatch
    ):
        monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "shared-secret")
        client = make_client(db=db)
        _strip_auth_overrides(client)

        response = client.post(
            "/api/customers/by_ids/", json=[], headers={INTERNAL_SERVICE_HEADER: "wrong"}
        )

        assert response.status_code == 401

    async def test_internal_service_credential_grants_access(self, make_client, db, monkeypatch):
        monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "shared-secret")
        customer = await _persist(db, CustomerFactory.build())
        client = make_client(db=db)
        _strip_auth_overrides(client)

        response = client.post(
            "/api/customers/by_ids/",
            json=[str(customer.id)],
            headers={INTERNAL_SERVICE_HEADER: "shared-secret"},
        )

        assert response.status_code == 200
        assert response.json()[0]["id"] == str(customer.id)

    async def test_authenticated_user_token_grants_access(self, make_client, db, monkeypatch):
        # Cross-tenant on purpose: donors/grantees resolve each other's
        # company via this route, and it is not tenant-scoped (see design.md).
        monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "shared-secret")
        customer = await _persist(db, CustomerFactory.build())
        client = make_client(db=db)
        _strip_auth_overrides(client)

        response = client.post(
            "/api/customers/by_ids/",
            json=[str(customer.id)],
            headers=_bearer(uuid4()),
        )

        assert response.status_code == 200
        assert response.json()[0]["id"] == str(customer.id)
