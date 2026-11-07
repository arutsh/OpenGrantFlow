"""Derived total_amount and the dashboard aggregates over it, on real Postgres numeric.
Skipped when Postgres is unreachable; every test rolls back its seed data."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.crud.budget_crud import get_funded_budgets_summary, get_funded_grantees
from app.crud.dashboard_crud import sum_committed_by_currency
from app.models.budget import BudgetModel
from shared.schemas.budget_schema import BudgetStatus
from tests.factories.budget import BudgetFactory, BudgetLineFactory

pytestmark = pytest.mark.anyio


@pytest.fixture
async def pg_session():
    db_url = make_url(settings.budget_database_url).set(drivername="postgresql+asyncpg")
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        conn = await engine.connect()
    except (OperationalError, OSError):
        await engine.dispose()
        pytest.skip(f"Postgres not reachable at {settings.budget_database_url}")
    outer = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    yield session
    await session.close()
    await outer.rollback()
    await conn.close()
    await engine.dispose()


@pytest.fixture
def ids():
    return {"donor": uuid.uuid4(), "grantee": uuid.uuid4(), "other_grantee": uuid.uuid4()}


async def _budget(session, owner_id, funder_id, *, lines, currency="EUR", rate="1", status=None):
    budget = BudgetFactory.build(
        owner_id=owner_id,
        funding_customer_id=funder_id,
        actual_currency=currency,
        estimated_exchange_rate=Decimal(rate) if rate is not None else None,
        status=status or BudgetStatus.confirmed,
    )
    session.add(budget)
    session.add_all(_line(budget, a) for a in lines)
    await session.flush()
    return budget


def _line(budget, amount):
    # No category: the factory's per-line "Personnel" breaks the per-budget unique name.
    return BudgetLineFactory.build(budget=budget, amount=Decimal(amount), category=None)


@pytest.fixture
async def seeded(pg_session, ids):
    donor, grantee, other = ids["donor"], ids["grantee"], ids["other_grantee"]
    budgets = {
        "fractional": await _budget(
            pg_session, grantee, donor, lines=["0.1", "0.2", "100"], rate="2"
        ),
        "second_eur": await _budget(pg_session, grantee, donor, lines=["10"], rate="4"),
        "usd": await _budget(pg_session, grantee, donor, lines=["1.5"], currency="USD", rate="0.5"),
        "draft": await _budget(
            pg_session, grantee, donor, lines=["1000"], status=BudgetStatus.draft
        ),
        "no_lines": await _budget(pg_session, grantee, donor, lines=[]),
        "no_rate": await _budget(pg_session, grantee, donor, lines=["999"], rate=None),
        "other_gbp": await _budget(pg_session, other, donor, lines=["7.25"], currency="GBP"),
    }
    pg_session.expunge_all()
    return budgets


def _by_currency(entries):
    return {e["currency"]: e["total_allocated"] for e in entries}


class TestDerivedTotalAmount:
    async def test_total_is_exact_line_sum(self, pg_session, seeded):
        row = await pg_session.scalar(
            select(BudgetModel).where(BudgetModel.id == seeded["fractional"].id)
        )
        assert isinstance(row.total_amount, Decimal)
        assert row.total_amount == Decimal("100.3")

    async def test_budget_without_lines_totals_zero(self, pg_session, seeded):
        row = await pg_session.scalar(
            select(BudgetModel).where(BudgetModel.id == seeded["no_lines"].id)
        )
        assert row.total_amount == Decimal(0)

    async def test_total_tracks_line_writes_without_recalculation(self, pg_session, seeded):
        budget_id = seeded["second_eur"].id
        pg_session.add(_line(await pg_session.get(BudgetModel, budget_id), "0.0001"))
        await pg_session.flush()
        total = await pg_session.scalar(
            select(BudgetModel.total_amount).where(BudgetModel.id == budget_id)
        )
        assert total == Decimal("10.0001")

    async def test_schema_has_budget_id_index_and_no_stored_total(self, pg_session):
        version = await pg_session.scalar(text("SELECT version_num FROM alembic_version"))
        if version != "000022":
            pytest.skip(f"database at {version}, not migrated to 000022")
        stored = await pg_session.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'budgets' AND column_name = 'total_amount'"
            )
        )
        index = await pg_session.scalar(
            text("SELECT to_regclass('ix_budget_lines_budget_id') IS NOT NULL")
        )
        assert stored == 0
        assert index is True


class TestAggregatesOverDerivedTotal:
    async def test_sum_committed_by_currency(self, pg_session, seeded, ids):
        rows = dict(await sum_committed_by_currency(pg_session, ids["grantee"]))
        # 100.3 / 2 + 10 / 4 + 0 / 1; draft and rate-less budgets are excluded.
        assert rows == {"EUR": Decimal("52.65"), "USD": Decimal("3")}
        assert all(isinstance(v, Decimal) for v in rows.values())

    async def test_get_funded_budgets_summary(self, pg_session, seeded, ids):
        summary = await get_funded_budgets_summary(pg_session, ids["donor"])
        assert summary["total_budgets"] == 7
        assert _by_currency(summary["total_allocated_by_currency"]) == {
            "EUR": Decimal("52.65"),
            "USD": Decimal("3"),
            "GBP": Decimal("7.25"),
        }

    async def test_get_funded_grantees(self, pg_session, seeded, ids):
        grantees = {
            str(g["owner_id"]): g for g in await get_funded_grantees(pg_session, ids["donor"])
        }
        assert set(grantees) == {str(ids["grantee"]), str(ids["other_grantee"])}

        grantee = grantees[str(ids["grantee"])]
        assert grantee["budgets_count"] == 6
        assert _by_currency(grantee["total_allocated_by_currency"]) == {
            "EUR": Decimal("52.65"),
            "USD": Decimal("3"),
        }

        other = grantees[str(ids["other_grantee"])]
        assert other["budgets_count"] == 1
        assert _by_currency(other["total_allocated_by_currency"]) == {"GBP": Decimal("7.25")}
