"""Adversarial tests for anonymous account creation (account-tenant-authz, group 1)."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from main import app
from app.db.session import get_db
from app.models.base import Base
from app.models.user import UserModel
from app.utils.security import decode_access_token
from tests.factories.user import CustomerFactory

PASSWORD = "Tr1cky-Horse-Battery-Staple!"


@pytest.fixture
async def db():
    """All tables: register → verify-email touches users, customers and sessions."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def anon_client(db):
    """Unauthenticated client; rate limiter and email queue stubbed so no Redis/broker is hit."""
    enqueue = MagicMock()
    with ExitStack() as stack:
        stack.enter_context(patch("main.init_publisher", AsyncMock()))
        stack.enter_context(patch("main.close_publisher", AsyncMock()))
        stack.enter_context(patch("app.api.auth_routes.is_locked_out", return_value=False))
        stack.enter_context(patch("app.api.auth_routes.record_failed_attempt"))
        stack.enter_context(patch("app.api.auth_routes.clear_failed_attempts"))
        stack.enter_context(
            patch("app.api.auth_routes.enqueue_verification_email", enqueue)
        )
        app.dependency_overrides[get_db] = lambda: db
        client = stack.enter_context(TestClient(app))
        client.enqueue_verification_email = enqueue
        try:
            yield client
        finally:
            app.dependency_overrides = {}


def _register_body(email, **extra):
    return {
        "email": email,
        "password": PASSWORD,
        "first_name": "Eve",
        "last_name": "Attacker",
        "consent_data_processing": True,
        **extra,
    }


async def _user_count(db):
    return (await db.execute(select(func.count()).select_from(UserModel))).scalar_one()


@pytest.mark.anyio
class TestLegacyCreateUserEndpointRemoved:
    async def test_post_users_rejected_and_creates_no_row(self, anon_client, db):
        before = await _user_count(db)

        response = anon_client.post(
            "/api/users/",
            json={"email": "eve@example.com", "role": "superuser", "status": "active"},
        )

        assert response.status_code in (404, 405)
        assert await _user_count(db) == before


@pytest.mark.anyio
class TestRegistrationIgnoresCompanyMembership:
    async def test_register_with_foreign_customer_id_creates_companyless_user(
        self, anon_client, db
    ):
        victim = CustomerFactory.build(name="Victim Org")
        db.add(victim)
        await db.commit()

        response = anon_client.post(
            "/api/register",
            json=_register_body("eve@example.com", customer_id=str(victim.id)),
        )

        assert response.status_code == 200
        user = (
            await db.execute(select(UserModel).where(UserModel.email == "eve@example.com"))
        ).scalar_one()
        assert user.customer_id is None
        assert user.role == "user"

    async def test_register_resend_verify_never_yields_privileged_token(self, anon_client, db):
        victim = CustomerFactory.build(name="Victim Org")
        db.add(victim)
        await db.commit()
        email = "eve@example.com"

        register = anon_client.post(
            "/api/register",
            json=_register_body(
                email, role="superuser", status="active", customer_id=str(victim.id)
            ),
        )
        assert register.status_code == 200

        anon_client.enqueue_verification_email.reset_mock()
        resend = anon_client.post("/api/auth/resend-verification", json={"email": email})
        assert resend.status_code == 200
        raw_token = anon_client.enqueue_verification_email.call_args.args[1]

        verify = anon_client.post(
            "/api/auth/verify-email", json={"email": email, "token": raw_token}
        )

        assert verify.status_code == 200
        claims = decode_access_token(verify.json()["access_token"])
        assert claims["role"] == "user"
        assert claims.get("customer_id") is None
