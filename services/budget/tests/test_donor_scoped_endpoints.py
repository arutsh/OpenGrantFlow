"""
Tests for the donor-scoped /budgets/funded/* endpoints (ticket #139).

Route-level tests mock the service layer (matching this service's existing
convention — see test_budget_routes.py) and cover the require_donor gate.
Crud-level tests hit a real sqlite session to verify the aggregation SQL
itself, including that a budget funded by a different donor is excluded.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

CUSTOMER_ID = str(uuid.uuid4())


class TestFundedBudgetsSummaryEndpoint:
    def test_donor_with_data(self, make_client):
        client = make_client(customer_id=CUSTOMER_ID, is_donor=True)
        with patch(
            "app.api.budget_routes.get_funded_budgets_summary_service",
            return_value={
                "total_budgets": 3,
                "total_allocated_by_currency": [{"currency": "GBP", "total_allocated": 4500.0}],
            },
        ):
            response = client.get("/api/v1/budgets/funded/summary")

        assert response.status_code == 200
        assert response.json() == {
            "total_budgets": 3,
            "total_allocated_by_currency": [{"currency": "GBP", "total_allocated": 4500.0}],
        }

    def test_donor_with_zero_funded_budgets(self, make_client):
        client = make_client(customer_id=CUSTOMER_ID, is_donor=True)
        with patch(
            "app.api.budget_routes.get_funded_budgets_summary_service",
            return_value={"total_budgets": 0, "total_allocated_by_currency": []},
        ):
            response = client.get("/api/v1/budgets/funded/summary")

        assert response.status_code == 200
        assert response.json() == {
            "total_budgets": 0,
            "total_allocated_by_currency": [],
        }

    def test_non_donor_gets_403(self, make_client):
        client = make_client(customer_id=CUSTOMER_ID, is_donor=False)
        response = client.get("/api/v1/budgets/funded/summary")

        assert response.status_code == 403


class TestFundedGranteesEndpoint:
    def test_donor_with_data(self, make_client):
        client = make_client(customer_id=CUSTOMER_ID, is_donor=True)
        grantee_id = str(uuid.uuid4())
        with patch(
            "app.api.budget_routes.get_funded_grantees_service",
            AsyncMock(
                return_value=[
                    {
                        "id": grantee_id,
                        "name": "Test NGO",
                        "country": "KE",
                        "budgets_count": 2,
                        "total_allocated_by_currency": [
                            {"currency": "GBP", "total_allocated": 1500.0}
                        ],
                    }
                ]
            ),
        ):
            response = client.get("/api/v1/budgets/funded/grantees")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["name"] == "Test NGO"
        assert body[0]["budgets_count"] == 2

    def test_non_donor_gets_403(self, make_client):
        client = make_client(customer_id=CUSTOMER_ID, is_donor=False)
        response = client.get("/api/v1/budgets/funded/grantees")

        assert response.status_code == 403


class TestFundedBudgetsListEndpoint:
    def test_donor_with_data(self, make_client):
        client = make_client(customer_id=CUSTOMER_ID, is_donor=True)
        budget_id = str(uuid.uuid4())
        with patch(
            "app.api.budget_routes.get_funded_budgets_service",
            AsyncMock(
                return_value=[
                    {
                        "id": budget_id,
                        "name": "Clean Water Project",
                        "status": "confirmed",
                        "total_amount": 2000.0,
                        "owner": {"id": str(uuid.uuid4()), "name": "Test NGO"},
                    }
                ]
            ),
        ):
            response = client.get("/api/v1/budgets/funded/")

        assert response.status_code == 200
        body = response.json()
        assert body[0]["owner"]["name"] == "Test NGO"
        assert body[0]["total_amount"] == 2000.0

    def test_non_donor_gets_403(self, make_client):
        client = make_client(customer_id=CUSTOMER_ID, is_donor=False)
        response = client.get("/api/v1/budgets/funded/")

        assert response.status_code == 403


@pytest.fixture
async def sqlite_session():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.base import Base
    from app.models.budget import BudgetModel, BudgetLineModel

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[BudgetModel.__table__, BudgetLineModel.__table__]
        )
    maker = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.mark.anyio
class TestFundedBudgetsCrud:
    """Direct coverage of the new aggregation queries, against a real sqlite session."""

    async def test_summary_totals_only_this_donors_budgets(self, sqlite_session):
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_budgets_summary

        session = sqlite_session
        donor_id = uuid.uuid4()
        other_donor_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="A",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=1000.0,
                actual_currency="GBP",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="B",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=500.0,
                actual_currency="GBP",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="C",
                owner_id=uuid.uuid4(),
                funding_customer_id=other_donor_id,
                local_currency="KES",
                total_amount=9999.0,
                actual_currency="GBP",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
        ):
            # Committed one at a time: BudgetModel.id's default returns a str,
            # not a uuid.UUID (unlike sibling models), which trips SQLAlchemy's
            # batched-insert sentinel matching when >1 row flushes at once.
            session.add(budget)
            await session.commit()

        summary = await get_funded_budgets_summary(session, donor_id)

        assert summary == {
            "total_budgets": 2,
            "total_allocated_by_currency": [{"currency": "GBP", "total_allocated": 1500.0}],
        }
        assert isinstance(summary["total_allocated_by_currency"][0]["total_allocated"], Decimal)

    async def test_summary_zero_for_donor_with_no_funded_budgets(self, sqlite_session):
        from app.crud.budget_crud import get_funded_budgets_summary

        session = sqlite_session
        summary = await get_funded_budgets_summary(session, uuid.uuid4())

        assert summary == {
            "total_budgets": 0,
            "total_allocated_by_currency": [],
        }

    async def test_summary_keeps_currencies_separate_not_blended(self, sqlite_session):
        """A donor funding budgets in different currencies must not get one
        blended sum mislabeled with an arbitrary currency (see #139 review)."""
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_budgets_summary

        session = sqlite_session
        donor_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="A",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=2400.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="B",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="UGX",
                total_amount=5000.0,
                actual_currency="USD",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
        ):
            session.add(budget)
            await session.commit()

        summary = await get_funded_budgets_summary(session, donor_id)

        assert summary["total_budgets"] == 2
        by_currency = {
            c["currency"]: c["total_allocated"] for c in summary["total_allocated_by_currency"]
        }
        assert by_currency == {"GBP": pytest.approx(3000.0), "USD": pytest.approx(5000.0)}

    async def test_summary_excludes_budgets_missing_a_usable_rate(self, sqlite_session):
        """A confirmed budget with no actual_currency/estimated_exchange_rate
        set (e.g. confirmed before those fields existed — no backfill, see
        design.md's migration plan) still counts toward total_budgets, but
        can't be converted into a donor-currency figure, so it's excluded
        from the currency-grouped total entirely rather than folded into
        another currency's total or silently zeroing it out — same
        "exclude rather than misrepresent" rule as the grantee dashboard's
        own committed-by-currency aggregation."""
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_budgets_summary

        session = sqlite_session
        donor_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="Has a rate",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=2400.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="Legacy confirmed budget — no commitment fields set",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=3000.0,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="Zero rate",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=1000.0,
                actual_currency="GBP",
                estimated_exchange_rate=0,
                status=BudgetStatus.confirmed,
            ),
        ):
            session.add(budget)
            await session.commit()

        summary = await get_funded_budgets_summary(session, donor_id)

        assert summary["total_budgets"] == 3
        assert summary["total_allocated_by_currency"] == [
            {"currency": "GBP", "total_allocated": pytest.approx(3000.0)}
        ]

    async def test_summary_excludes_unconfirmed_budgets_even_with_a_usable_rate(
        self, sqlite_session
    ):
        """A draft budget with actual_currency/estimated_exchange_rate already
        set still counts toward total_budgets, but doesn't contribute to the
        currency-grouped figure until it's confirmed — a draft's total can
        still change."""
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_budgets_summary

        session = sqlite_session
        donor_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="A — confirmed",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=2400.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="B — still draft",
                owner_id=uuid.uuid4(),
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=9000.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.draft,
            ),
        ):
            session.add(budget)
            await session.commit()

        summary = await get_funded_budgets_summary(session, donor_id)

        assert summary["total_budgets"] == 2
        assert summary["total_allocated_by_currency"] == [
            {"currency": "GBP", "total_allocated": pytest.approx(3000.0)}
        ]

    async def test_grantees_groups_by_owner_across_multiple_budgets(self, sqlite_session):
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_grantees

        session = sqlite_session
        donor_id = uuid.uuid4()
        grantee_id = uuid.uuid4()
        other_grantee_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="A",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=100.0,
                actual_currency="GBP",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="B",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=200.0,
                actual_currency="GBP",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="C",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=300.0,
                actual_currency="GBP",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="D",
                owner_id=other_grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=50.0,
                actual_currency="GBP",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
        ):
            session.add(budget)
            await session.commit()

        grantees = await get_funded_grantees(session, donor_id)
        by_owner = {g["owner_id"]: g for g in grantees}

        assert by_owner[grantee_id]["budgets_count"] == 3
        assert by_owner[grantee_id]["total_allocated_by_currency"] == [
            {"currency": "GBP", "total_allocated": pytest.approx(600.0)}
        ]
        assert by_owner[other_grantee_id]["budgets_count"] == 1
        assert by_owner[other_grantee_id]["total_allocated_by_currency"] == [
            {"currency": "GBP", "total_allocated": pytest.approx(50.0)}
        ]

    async def test_grantees_keeps_currencies_separate_not_blended(self, sqlite_session):
        """Same grantee funded via budgets in two different currencies must not
        be blended into one mislabeled sum (see #139 review)."""
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_grantees

        session = sqlite_session
        donor_id = uuid.uuid4()
        grantee_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="A",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=2400.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="B",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="UGX",
                total_amount=5000.0,
                actual_currency="USD",
                estimated_exchange_rate=1.0,
                status=BudgetStatus.confirmed,
            ),
        ):
            session.add(budget)
            await session.commit()

        grantees = await get_funded_grantees(session, donor_id)
        assert len(grantees) == 1
        grantee = grantees[0]
        assert grantee["budgets_count"] == 2
        by_currency = {
            c["currency"]: c["total_allocated"] for c in grantee["total_allocated_by_currency"]
        }
        assert by_currency == {"GBP": pytest.approx(3000.0), "USD": pytest.approx(5000.0)}

    async def test_grantees_excludes_budget_missing_a_usable_rate_from_currency_total(
        self, sqlite_session
    ):
        """Regression test: a confirmed budget with no actual_currency/
        estimated_exchange_rate set (e.g. confirmed before those fields
        existed — no backfill, see design.md's migration plan) still counts
        toward budgets_count, but can't be converted, so it's excluded from
        the currency-grouped total rather than silently dropping it or
        folding it into another currency."""
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_grantees

        session = sqlite_session
        donor_id = uuid.uuid4()
        grantee_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="Has a rate",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=2400.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="Legacy confirmed budget — no commitment fields set",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=3000.0,
                status=BudgetStatus.confirmed,
            ),
        ):
            session.add(budget)
            await session.commit()

        grantees = await get_funded_grantees(session, donor_id)
        assert len(grantees) == 1
        grantee = grantees[0]
        assert grantee["budgets_count"] == 2
        assert grantee["total_allocated_by_currency"] == [
            {"currency": "GBP", "total_allocated": pytest.approx(3000.0)}
        ]

    async def test_grantees_excludes_unconfirmed_budgets_from_currency_total(self, sqlite_session):
        """A grantee's draft budget with actual_currency/estimated_exchange_rate
        already set still counts toward budgets_count, but doesn't contribute
        to the currency-grouped total until it's confirmed."""
        from app.models.budget import BudgetModel, BudgetStatus
        from app.crud.budget_crud import get_funded_grantees

        session = sqlite_session
        donor_id = uuid.uuid4()
        grantee_id = uuid.uuid4()

        for budget in (
            BudgetModel(
                name="A — confirmed",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=2400.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.confirmed,
            ),
            BudgetModel(
                name="B — still draft",
                owner_id=grantee_id,
                funding_customer_id=donor_id,
                local_currency="KES",
                total_amount=9000.0,
                actual_currency="GBP",
                estimated_exchange_rate=0.8,
                status=BudgetStatus.draft,
            ),
        ):
            session.add(budget)
            await session.commit()

        grantees = await get_funded_grantees(session, donor_id)
        assert len(grantees) == 1
        grantee = grantees[0]
        assert grantee["budgets_count"] == 2
        assert grantee["total_allocated_by_currency"] == [
            {"currency": "GBP", "total_allocated": pytest.approx(3000.0)}
        ]

    async def test_list_budgets_funding_filter_excludes_other_donors(self, sqlite_session):
        from app.models.budget import BudgetModel
        from app.crud.budget_crud import list_budgets

        session = sqlite_session
        donor_id = uuid.uuid4()
        other_donor_id = uuid.uuid4()

        mine = BudgetModel(name="Mine", owner_id=uuid.uuid4(), funding_customer_id=donor_id)
        theirs = BudgetModel(
            name="Theirs", owner_id=uuid.uuid4(), funding_customer_id=other_donor_id
        )
        session.add(mine)
        await session.commit()
        session.add(theirs)
        await session.commit()

        results = await list_budgets(session, funding_customer_id=donor_id)

        assert [b.name for b in results] == ["Mine"]
