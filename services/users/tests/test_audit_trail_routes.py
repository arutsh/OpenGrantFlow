"""Real-JWT route tests: make_client's get_validated_user override would skip the
contextvar-setting code these tests need to exercise."""

from datetime import datetime, timezone
from uuid import uuid4

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.bug_report_routes import get_db as bug_report_get_db
from app.api.donor_grantee_routes import get_db as donor_grantee_get_db
from app.models.base import Base
from app.models.bug_report import BugReportModel
from app.models.customer import DonorGranteeModel
from main import app
from shared.security import session_revocation
from tests.conftest import _token_for
from tests.factories.user import CustomerFactory

pytestmark = pytest.mark.anyio


@pytest.fixture
async def bug_reports_db():
    """conftest's `db` fixture doesn't include bug_reports — separate table set."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[BugReportModel.__table__])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    monkeypatch.setattr(session_revocation, "_redis_client", fakeredis.FakeStrictRedis())


class TestBugReportAuditTrail:
    async def test_created_by_populated_via_real_auth_chain(self, bug_reports_db):
        app.dependency_overrides[bug_report_get_db] = lambda: bug_reports_db
        try:
            user_id = str(uuid4())
            client = TestClient(app)

            response = client.post(
                "/api/bug-reports/",
                headers={"Authorization": f"Bearer {_token_for(user_id)}"},
                data={
                    "description": "Something broke",
                    "page_path": "/budgets/123",
                    "user_agent": "Mozilla/5.0",
                    "client_timestamp": datetime(
                        2026, 9, 19, tzinfo=timezone.utc
                    ).isoformat(),
                },
            )
        finally:
            del app.dependency_overrides[bug_report_get_db]

        assert response.status_code == 200
        bug_report = (
            await bug_reports_db.execute(
                select(BugReportModel).where(BugReportModel.id == response.json()["id"])
            )
        ).scalar_one()
        assert str(bug_report.created_by) == user_id
        assert bug_report.updated_by is None


class TestDonorGranteeAuditTrail:
    async def test_created_by_populated_via_real_auth_chain(self, db):
        donor = CustomerFactory.build(name="Donor Org", is_donor=True)
        grantee = CustomerFactory.build(name="Grantee Org", is_ngo=True)
        db.add_all([donor, grantee])
        await db.commit()

        app.dependency_overrides[donor_grantee_get_db] = lambda: db
        try:
            user_id = str(uuid4())
            token = _token_for(user_id, customer_id=str(donor.id), is_donor=True)
            client = TestClient(app)

            response = client.post(
                "/api/donor-grantees/",
                headers={"Authorization": f"Bearer {token}"},
                json={"grantee_id": str(grantee.id)},
            )
        finally:
            del app.dependency_overrides[donor_grantee_get_db]

        assert response.status_code == 200
        donor_grantee = (
            await db.execute(
                select(DonorGranteeModel).where(DonorGranteeModel.id == response.json()["id"])
            )
        ).scalar_one()
        assert str(donor_grantee.created_by) == user_id
        assert donor_grantee.updated_by is None
