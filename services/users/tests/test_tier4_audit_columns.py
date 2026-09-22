"""audit-mixin-rollout-tier4 group 3: created_by/updated_by for CustomerModel/UserModel.
Real-JWT route tests — overriding get_validated_user would skip the contextvar."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_db as users_get_db
from app.models.customer import CustomerModel
from app.models.user import UserModel
from main import app
from tests.conftest import _token_for
from tests.factories.user import CustomerFactory, UserModelFactory

pytestmark = pytest.mark.anyio


class TestUserSelfRegistrationAuditTrail:
    async def test_created_by_stays_null_with_no_authenticated_actor(self, db):
        app.dependency_overrides[users_get_db] = lambda: db
        try:
            with (
                patch("app.api.auth_routes.enqueue_verification_email"),
                patch(
                    "app.api.auth_routes.set_email_verification_token",
                    AsyncMock(return_value="tok"),
                ),
            ):
                client = TestClient(app)
                response = client.post(
                    "/api/register",
                    json={
                        "email": "new-signup@example.com",
                        "password": "Correct-Horse-1",
                        "consent_data_processing": True,
                    },
                )
        finally:
            del app.dependency_overrides[users_get_db]

        assert response.status_code == 200
        user = (
            await db.execute(
                select(UserModel).where(UserModel.email == "new-signup@example.com")
            )
        ).scalar_one()
        assert user.created_by is None


class TestAdminInviteAuditTrail:
    async def test_created_by_populated_via_real_auth_chain(self, db):
        customer = CustomerFactory.build()
        admin = UserModelFactory.build(role="admin", customer_id=customer.id)
        db.add_all([customer, admin])
        await db.commit()

        app.dependency_overrides[users_get_db] = lambda: db
        try:
            token = _token_for(str(admin.id), role="admin", customer_id=str(customer.id))
            with patch("app.api.user_routes.enqueue_invite_email"):
                client = TestClient(app)
                response = client.post(
                    "/api/users/invite",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"email": "invitee@example.com", "role": "user"},
                )
        finally:
            del app.dependency_overrides[users_get_db]

        assert response.status_code == 200
        invited = (
            await db.execute(
                select(UserModel).where(UserModel.email == "invitee@example.com")
            )
        ).scalar_one()
        assert str(invited.created_by) == str(admin.id)


class TestCustomerCreationAuditTrail:
    async def test_created_by_populated_via_real_auth_chain(self, db):
        actor = UserModelFactory.build()
        db.add(actor)
        await db.commit()

        app.dependency_overrides[users_get_db] = lambda: db
        try:
            user_id = str(actor.id)
            token = _token_for(user_id)
            client = TestClient(app)
            response = client.post(
                "/api/customers/",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": "New Org",
                    "country": "GB",
                    "currency": "GBP",
                    "is_ngo": True,
                    "is_donor": False,
                },
            )
        finally:
            del app.dependency_overrides[users_get_db]

        assert response.status_code == 200
        customer = (
            await db.execute(
                select(CustomerModel).where(CustomerModel.id == response.json()["id"])
            )
        ).scalar_one()
        assert str(customer.created_by) == user_id


class TestCustomerUpdateAuditTrail:
    async def test_updated_by_populated_on_update(self, db):
        customer = CustomerFactory.build()
        admin = UserModelFactory.build(role="admin", customer_id=customer.id)
        db.add_all([customer, admin])
        await db.commit()

        app.dependency_overrides[users_get_db] = lambda: db
        try:
            admin_id = str(admin.id)
            token = _token_for(admin_id, role="admin", customer_id=str(customer.id))
            client = TestClient(app)
            response = client.patch(
                f"/api/customers/{customer.id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"name": "Renamed Org"},
            )
        finally:
            del app.dependency_overrides[users_get_db]

        assert response.status_code == 200
        await db.refresh(customer)
        assert str(customer.updated_by) == admin_id
