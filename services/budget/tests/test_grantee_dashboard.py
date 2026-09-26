"""
Tests for ticket #184: grantee-dashboard aggregation endpoint
(GET /budgets/dashboard/summary).

Same real-sqlite-session convention as test_currency_ledger.py — needs
Budget/BudgetLine/Report/ReportLine/FundingReceipt/CurrencyConversion tables,
so this file overrides conftest's module-level `db` fixture with a wider one.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.budget import BudgetModel, BudgetLineModel, BudgetCategoryModel
from app.models.report import ReportModel, ReportLineModel, AttachmentModel
from app.models.currency_ledger import (
    FundingReceiptModel,
    CurrencyConversionModel,
    ReportLineConversionAllocationModel,
)
from app.schemas.budget_schema import BudgetStatus
from app.schemas.report_schema import ReportStatus
from app.services.budget_services import get_grantee_dashboard_summary_service

OWNER_ID = str(uuid4())
OTHER_OWNER_ID = str(uuid4())
FUNDER_ID = str(uuid4())


@pytest.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                BudgetModel.__table__,
                BudgetLineModel.__table__,
                BudgetCategoryModel.__table__,
                ReportModel.__table__,
                ReportLineModel.__table__,
                AttachmentModel.__table__,
                FundingReceiptModel.__table__,
                CurrencyConversionModel.__table__,
                ReportLineConversionAllocationModel.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _make_budget(
    db,
    owner_id=OWNER_ID,
    funding_customer_id=None,
    external_funder_name=None,
    status=BudgetStatus.confirmed,
    total_amount=0.0,
    local_currency="GBP",
    actual_currency=None,
    donor_total_amount=None,
    estimated_exchange_rate=None,
    name="Test Budget",
):
    budget = BudgetModel(
        name=name,
        owner_id=owner_id,
        funding_customer_id=funding_customer_id,
        external_funder_name=external_funder_name,
        status=status,
        total_amount=total_amount,
        local_currency=local_currency,
        actual_currency=actual_currency,
        donor_total_amount=donor_total_amount,
        estimated_exchange_rate=estimated_exchange_rate,
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


async def _make_receipt(db, budget_id, amount):
    receipt = FundingReceiptModel(budget_id=budget_id, amount=amount, received_at=date(2026, 1, 1))
    db.add(receipt)
    await db.commit()
    return receipt


async def _make_conversion(db, budget_id, donor_amount, local_amount):
    conversion = CurrencyConversionModel(
        budget_id=budget_id,
        donor_amount=donor_amount,
        local_amount=local_amount,
        converted_at=date(2026, 1, 2),
    )
    db.add(conversion)
    await db.commit()
    return conversion


async def _make_spend(db, budget_id, amount):
    report = ReportModel(
        budget_id=budget_id,
        name="Report",
        status=ReportStatus.draft,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    line = BudgetLineModel(budget_id=budget_id, description="Line", amount=amount)
    db.add(line)
    await db.commit()
    await db.refresh(line)
    report_line = ReportLineModel(
        report_id=report.id,
        budget_line_id=line.id,
        description="Spend",
        amount=amount,
        expense_date=date(2026, 2, 1),
    )
    db.add(report_line)
    await db.commit()
    return report_line


@pytest.mark.anyio
class TestBudgetCountsByStatus:
    async def test_counts_are_correct_per_status(self, db):
        await _make_budget(db, status=BudgetStatus.draft)
        await _make_budget(db, status=BudgetStatus.draft)
        await _make_budget(db, status=BudgetStatus.confirmed)
        await _make_budget(db, status=BudgetStatus.archived)
        # A different owner's budgets must not be counted.
        await _make_budget(db, owner_id=OTHER_OWNER_ID, status=BudgetStatus.confirmed)

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        counts = {c.status: c.count for c in result.budget_counts_by_status}
        assert counts == {
            BudgetStatus.draft: 2,
            BudgetStatus.confirmed: 1,
            BudgetStatus.archived: 1,
        }


@pytest.mark.anyio
class TestCommittedByCurrency:
    async def test_committed_uses_total_amount_and_estimated_rate_not_donor_total_amount(self, db):
        # Promise is 10000 EUR, but only 6000 GBP of lines have actually been
        # built so far — committed must reflect the latter, not the former
        # (design.md Decision 8).
        await _make_budget(
            db,
            total_amount=6000.0,
            actual_currency="EUR",
            estimated_exchange_rate=0.8,
            donor_total_amount=10000.0,
        )

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        assert len(result.committed_by_currency) == 1
        figure = result.committed_by_currency[0]
        assert figure.currency == "EUR"
        assert figure.total_allocated == pytest.approx(7500.0)  # 6000 / 0.8
        assert isinstance(figure.total_allocated, Decimal)

    async def test_excludes_budgets_missing_a_usable_rate(self, db):
        await _make_budget(
            db, total_amount=1000.0, actual_currency="EUR", estimated_exchange_rate=None
        )
        await _make_budget(
            db, total_amount=1000.0, actual_currency=None, estimated_exchange_rate=0.8
        )
        await _make_budget(
            db, total_amount=1000.0, actual_currency="EUR", estimated_exchange_rate=0
        )

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        assert result.committed_by_currency == []

    async def test_excludes_non_confirmed_budgets(self, db):
        await _make_budget(
            db,
            status=BudgetStatus.draft,
            total_amount=1000.0,
            actual_currency="EUR",
            estimated_exchange_rate=0.8,
        )

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        assert result.committed_by_currency == []

    async def test_keeps_currencies_separate_not_blended(self, db):
        await _make_budget(
            db, total_amount=800.0, actual_currency="EUR", estimated_exchange_rate=0.8, name="A"
        )
        await _make_budget(
            db, total_amount=500.0, actual_currency="USD", estimated_exchange_rate=1.0, name="B"
        )

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        by_currency = {f.currency: f.total_allocated for f in result.committed_by_currency}
        assert by_currency == {"EUR": pytest.approx(1000.0), "USD": pytest.approx(500.0)}


@pytest.mark.anyio
class TestReceivedAndConversionProgress:
    async def test_received_sums_receipts_scoped_to_confirmed_budgets(self, db):
        budget = await _make_budget(db, actual_currency="EUR")
        await _make_receipt(db, budget.id, 4000.0)
        await _make_receipt(db, budget.id, 1000.0)
        draft_budget = await _make_budget(db, status=BudgetStatus.draft, actual_currency="EUR")
        await _make_receipt(db, draft_budget.id, 9999.0)

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        received = {f.currency: f.total_allocated for f in result.received_by_currency}
        assert received == {"EUR": 5000.0}

    async def test_conversion_progress_percent_correct_per_currency(self, db):
        budget = await _make_budget(db, actual_currency="EUR")
        await _make_receipt(db, budget.id, 10000.0)
        await _make_conversion(db, budget.id, donor_amount=4000.0, local_amount=3200.0)

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        assert len(result.conversion_progress_by_currency) == 1
        progress = result.conversion_progress_by_currency[0]
        assert progress.currency == "EUR"
        assert progress.received == 10000.0
        assert progress.converted == 4000.0
        assert progress.percent == pytest.approx(40.0)
        assert isinstance(progress.received, Decimal)
        assert isinstance(progress.converted, Decimal)

    async def test_conversion_progress_zero_percent_when_nothing_received(self, db):
        budget = await _make_budget(db, actual_currency="EUR")
        await _make_conversion(db, budget.id, donor_amount=100.0, local_amount=80.0)

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        progress = result.conversion_progress_by_currency[0]
        assert progress.received == 0.0
        assert progress.percent == 0.0


@pytest.mark.anyio
class TestBudgetBreakdown:
    async def test_one_row_per_confirmed_budget_with_correct_figures(self, db):
        budget = await _make_budget(
            db,
            name="Water Project",
            funding_customer_id=FUNDER_ID,
            external_funder_name="Acme Foundation",
            local_currency="GBP",
        )
        await _make_conversion(db, budget.id, donor_amount=1000.0, local_amount=800.0)
        await _make_spend(db, budget.id, 300.0)
        # A non-confirmed budget must not appear in the breakdown.
        await _make_budget(db, status=BudgetStatus.draft)

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        assert len(result.budget_breakdown) == 1
        row = result.budget_breakdown[0]
        assert row.budget_id == budget.id
        assert row.budget_name == "Water Project"
        assert str(row.funding_customer_id) == FUNDER_ID
        assert row.external_funder_name == "Acme Foundation"
        assert row.local_currency == "GBP"
        assert row.converted == 800.0
        assert row.spent == 300.0
        assert row.remaining == 500.0
        assert isinstance(row.remaining, Decimal)

    async def test_confirmed_budget_with_no_conversions_or_spend_shows_zeroes(self, db):
        budget = await _make_budget(db)

        result = await get_grantee_dashboard_summary_service(OWNER_ID, db)

        [row] = result.budget_breakdown
        assert row.budget_id == budget.id
        assert row.converted == 0.0
        assert row.spent == 0.0
        assert row.remaining == 0.0


class TestDashboardSummaryRouteWiring:
    """Confirms the static /dashboard/summary path isn't swallowed by the
    /{budget_id} catch-all route registered later in budget_routes.py."""

    def test_route_delegates_to_service(self, make_client):
        client = make_client()
        with patch(
            "app.api.budget_routes.get_grantee_dashboard_summary_service",
            return_value={
                "budget_counts_by_status": [],
                "committed_by_currency": [],
                "received_by_currency": [],
                "conversion_progress_by_currency": [],
                "budget_breakdown": [],
            },
        ) as mock_service:
            response = client.get("/api/v1/budgets/dashboard/summary")

        assert response.status_code == 200
        assert response.json() == {
            "budget_counts_by_status": [],
            "committed_by_currency": [],
            "received_by_currency": [],
            "conversion_progress_by_currency": [],
            "budget_breakdown": [],
        }
        mock_service.assert_called_once()


@pytest.mark.anyio
class TestNoCustomerId:
    async def test_returns_empty_summary_when_customer_id_missing(self, db):
        result = await get_grantee_dashboard_summary_service(None, db)

        assert result.budget_counts_by_status == []
        assert result.committed_by_currency == []
        assert result.received_by_currency == []
        assert result.conversion_progress_by_currency == []
        assert result.budget_breakdown == []
