"""An impersonation token is exactly "admin of the impersonated company" on every
users-service write (account-tenant-authz group 3)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.db.session import get_db
from app.models.base import Base
from app.models.privileged_access_log import PrivilegedAccessLog
from app.services.privileged_access_audit import write_privileged_access_log
from shared.security.privileged_access import (
    make_privileged_access_sink,
    register_privileged_access_sink,
)
from tests.conftest import _token_for
from tests.factories.user import CustomerFactory, UserModelFactory

pytestmark = pytest.mark.anyio


@pytest.fixture
async def db():
    """All tables: the write routes below touch users, customers and sessions."""
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
async def tenants(db):
    """A superuser impersonating company A, and an admin + member in company B."""
    customer_a = CustomerFactory.build(name="Company A")
    customer_b = CustomerFactory.build(name="Company B")
    superuser = UserModelFactory.build(role="superuser", status="active")
    b_admin = UserModelFactory.build(customer_id=customer_b.id, role="admin", status="active")
    b_member = UserModelFactory.build(customer_id=customer_b.id, role="user", status="active")
    db.add_all([customer_a, customer_b, superuser, b_admin, b_member])
    await db.commit()
    return {
        "a": customer_a,
        "b": customer_b,
        "superuser": superuser,
        "b_admin": b_admin,
        "b_member": b_member,
    }


class TestImpersonationCannotWriteOutsideItsTenant:
    @pytest.mark.parametrize(
        "method, path, body",
        [
            ("PATCH", "/api/users/{b_member}/role", {"role": "admin"}),
            ("DELETE", "/api/users/{b_member}/remove", None),
            ("PATCH", "/api/customers/{b}", {"name": "Hijacked"}),
            ("POST", "/api/customers/{b}/deactivate", None),
            ("PATCH", "/api/users/{b_member}/", {"first_name": "Hijacked"}),
            ("DELETE", "/api/users/{b_member}", None),
        ],
    )
    async def test_write_targeting_company_b_is_403(
        self, make_client, db, tenants, method, path, body
    ):
        client = make_client(
            db=db,
            user_id=tenants["superuser"].id,
            role="admin",
            customer_id=str(tenants["a"].id),
            is_impersonating=True,
        )
        url = path.format(b=tenants["b"].id, b_member=tenants["b_member"].id)

        response = client.request(method, url, json=body)

        assert response.status_code == 403
        for obj in (tenants["b"], tenants["b_member"]):
            await db.refresh(obj)
        assert tenants["b"].name == "Company B"
        assert tenants["b"].deactivated_at is None
        assert tenants["b_member"].role == "user"
        assert tenants["b_member"].first_name != "Hijacked"
        assert tenants["b_member"].deleted_at is None
        assert str(tenants["b_member"].customer_id) == str(tenants["b"].id)


class TestImpersonatedDeactivationAudit:
    async def test_log_row_records_the_real_superuser(self, db, tenants):
        """Real JWT through get_validated_user, so the privileged-access sink actually runs."""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine, tables=[PrivilegedAccessLog.__table__])
        log_session = sessionmaker(bind=engine)()
        register_privileged_access_sink(
            make_privileged_access_sink(lambda: log_session, PrivilegedAccessLog)
        )
        app.dependency_overrides[get_db] = lambda: db
        try:
            token = _token_for(
                str(tenants["superuser"].id),
                role="admin",
                customer_id=str(tenants["a"].id),
                is_impersonating=True,
            )
            response = TestClient(app).post(
                f"/api/customers/{tenants['a'].id}/deactivate",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            register_privileged_access_sink(write_privileged_access_log)
            del app.dependency_overrides[get_db]

        assert response.status_code == 200
        [row] = log_session.query(PrivilegedAccessLog).all()
        assert str(row.actor_user_id) == str(tenants["superuser"].id)
        assert str(row.customer_id) == str(tenants["a"].id)
        assert row.method == "POST"
        assert row.path == f"/api/customers/{tenants['a'].id}/deactivate"
