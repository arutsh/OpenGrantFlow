"""
Tests for ticket #148: currency ledger FIFO allocation, and retroactive
backfill on a later conversion (design.md's 2026-07-26 amended note).

Same real-sqlite-session convention as test_report_line_routes.py.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.budget import BudgetModel, BudgetLineModel
from app.models.report import ReportModel
from app.models.currency_ledger import ReportLineConversionAllocationModel
from app.crud.currency_conversion_crud import list_unconsumed_lots, list_unsatisfied_report_lines
from app.crud.report_line_crud import list_report_lines
from app.schemas.budget_schema import BudgetStatus
from app.schemas.report_schema import ReportStatus
from app.schemas.report_line_schema import ReportLineCreate, ReportLineUpdate
from app.schemas.currency_ledger_schema import FundingReceiptCreate, CurrencyConversionCreate
from app.services.report_line_services import (
    create_report_line_service,
    update_report_line_service,
)
from app.core.exceptions import DomainError, PermissionDenied
from app.services.currency_ledger_services import (
    record_receipt_service,
    record_conversion_service,
    get_ledger_balance_service,
    list_funding_receipts_service,
    list_currency_conversions_service,
)
from tests.factories.user import ValidUserFactory

OWNER_ID = str(uuid4())
FUNDER_ID = str(uuid4())
STRANGER_ID = str(uuid4())


def _valid_user(customer_id=OWNER_ID):
    return ValidUserFactory(customer_id=customer_id)


async def _make_budget(
    db,
    owner_id=OWNER_ID,
    funding_customer_id=None,
    local_currency="USD",
    actual_currency="EUR",
):
    budget = BudgetModel(
        name="Test Budget",
        owner_id=owner_id,
        funding_customer_id=funding_customer_id,
        status=BudgetStatus.confirmed,
        start_date=date(2026, 1, 1),
        duration_months=12,
        local_currency=local_currency,
        actual_currency=actual_currency,
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


async def _make_budget_line(db, budget_id, amount=1000.0):
    line = BudgetLineModel(budget_id=budget_id, description="Admin costs", amount=amount)
    db.add(line)
    await db.commit()
    await db.refresh(line)
    return line


async def _make_report(db, budget_id, status=ReportStatus.draft):
    report = ReportModel(
        budget_id=budget_id,
        name="Report",
        status=status,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def _make_expense(db, report, budget_line, amount):
    return await create_report_line_service(
        db,
        _valid_user(),
        ReportLineCreate(
            report_id=report.id,
            budget_line_id=budget_line.id,
            description="Expense",
            amount=amount,
            expense_date=date(2026, 6, 15),
        ),
    )


async def _record_receipt(db, budget, amount, received_at):
    return await record_receipt_service(
        db,
        _valid_user(),
        FundingReceiptCreate(budget_id=budget.id, amount=amount, received_at=received_at),
    )


async def _record_conversion(db, budget, donor_amount, local_amount, converted_at):
    return await record_conversion_service(
        db,
        _valid_user(),
        CurrencyConversionCreate(
            budget_id=budget.id,
            donor_amount=donor_amount,
            local_amount=local_amount,
            converted_at=converted_at,
        ),
    )


async def _allocations_for(db, report_line_id):
    result = await db.execute(
        select(ReportLineConversionAllocationModel).filter_by(report_line_id=report_line_id)
    )
    return result.scalars().all()


@pytest.mark.anyio
class TestFifoAllocation:
    async def test_single_lot_fully_covers_expense(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=550.0, converted_at=date(2026, 1, 2)
        )

        expense = await _make_expense(db, report, budget_line, amount=300.0)

        allocations = await _allocations_for(db, expense.id)
        assert len(allocations) == 1
        assert allocations[0].amount_allocated == 300.0

    async def test_expense_splits_across_two_lots(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=200.0, local_amount=220.0, converted_at=date(2026, 1, 2)
        )
        await _record_conversion(
            db, budget, donor_amount=300.0, local_amount=330.0, converted_at=date(2026, 1, 5)
        )

        expense = await _make_expense(db, report, budget_line, amount=400.0)

        allocations = sorted(
            await _allocations_for(db, expense.id), key=lambda a: a.amount_allocated
        )
        assert [a.amount_allocated for a in allocations] == [180.0, 220.0]


@pytest.mark.anyio
class TestOverspendAndBackfill:
    async def test_overspend_leaves_remainder_unsatisfied(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=550.0, converted_at=date(2026, 1, 2)
        )

        expense = await _make_expense(db, report, budget_line, amount=800.0)

        allocations = await _allocations_for(db, expense.id)
        assert len(allocations) == 1
        assert allocations[0].amount_allocated == 550.0

        balance = await get_ledger_balance_service(db, _valid_user(), budget.id)
        assert balance.local_balance == pytest.approx(550.0 - 800.0)

    async def test_next_conversion_backfills_the_overspent_expense(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=550.0, converted_at=date(2026, 1, 2)
        )
        expense = await _make_expense(db, report, budget_line, amount=800.0)

        second_conversion = await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=560.0, converted_at=date(2026, 1, 6)
        )

        allocations = await _allocations_for(db, expense.id)
        assert len(allocations) == 2
        assert sum(a.amount_allocated for a in allocations) == pytest.approx(800.0)

        backfilled = [a for a in allocations if a.conversion_id == second_conversion.id]
        assert len(backfilled) == 1
        assert backfilled[0].amount_allocated == pytest.approx(250.0)

        balance = await get_ledger_balance_service(db, _valid_user(), budget.id)
        assert balance.local_balance == pytest.approx(310.0)

    async def test_oldest_unsatisfied_expense_backfilled_first(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=100.0, local_amount=100.0, converted_at=date(2026, 1, 1)
        )
        # 100 covered by the existing lot, 200 left unsatisfied.
        first_expense = await _make_expense(db, report, budget_line, amount=300.0)
        # No lots left at all — fully unsatisfied.
        second_expense = await _make_expense(db, report, budget_line, amount=150.0)
        # Stagger created_at so "oldest first" is unambiguous for this assertion.
        first_expense.created_at = datetime(2026, 1, 3, 0, 0, 0)
        second_expense.created_at = datetime(2026, 1, 3, 0, 0, 1)
        await db.commit()

        new_conversion = await _record_conversion(
            db, budget, donor_amount=180.0, local_amount=200.0, converted_at=date(2026, 1, 10)
        )

        first_allocations = await _allocations_for(db, first_expense.id)
        second_allocations = await _allocations_for(db, second_expense.id)
        assert sum(a.amount_allocated for a in first_allocations) == pytest.approx(300.0)
        assert sum(a.amount_allocated for a in second_allocations) == pytest.approx(0.0)
        assert any(a.conversion_id == new_conversion.id for a in first_allocations)


@pytest.mark.anyio
class TestPerCurrencyBalance:
    async def test_balance_reported_separately_per_currency(self, db):
        budget = await _make_budget(db, local_currency="USD", actual_currency="EUR")
        await _record_receipt(db, budget, amount=1000.0, received_at=date(2026, 1, 1))
        await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=550.0, converted_at=date(2026, 1, 2)
        )

        balance = await get_ledger_balance_service(db, _valid_user(), budget.id)

        assert balance.actual_currency == "EUR"
        assert balance.donor_balance == pytest.approx(1000.0 - 500.0)
        assert balance.local_currency == "USD"
        assert balance.local_balance == pytest.approx(550.0)


@pytest.mark.anyio
class TestExactAllocation:
    async def test_fractional_expense_splits_exactly_across_lots(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        oldest = await _record_conversion(
            db, budget, donor_amount=30, local_amount="33.37", converted_at=date(2026, 1, 2)
        )
        await _record_conversion(
            db, budget, donor_amount=900, local_amount=1000, converted_at=date(2026, 1, 5)
        )

        expense = await _make_expense(db, report, budget_line, amount="100.10")

        allocations = await _allocations_for(db, expense.id)
        by_lot = {a.conversion_id: a.amount_allocated for a in allocations}
        assert by_lot[oldest.id] == Decimal("33.37")
        assert sorted(by_lot.values()) == [Decimal("33.37"), Decimal("66.73")]
        assert sum(by_lot.values()) == Decimal("100.10")
        remaining_lots = await list_unconsumed_lots(db, budget.id)
        assert oldest.id not in {lot.id for lot, _ in remaining_lots}

    async def test_tiny_remainder_is_recorded_as_unsatisfied(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=90, local_amount=100, converted_at=date(2026, 1, 2)
        )

        expense = await _make_expense(db, report, budget_line, amount="100.0001")

        allocations = await _allocations_for(db, expense.id)
        assert [a.amount_allocated for a in allocations] == [Decimal("100")]
        unsatisfied = await list_unsatisfied_report_lines(db, budget.id)
        assert [(line.id, remaining) for line, remaining in unsatisfied] == [
            (expense.id, Decimal("0.0001"))
        ]

    async def test_ledger_balance_is_exact(self, db):
        budget = await _make_budget(db)
        await _record_receipt(db, budget, amount=0.1, received_at=date(2026, 1, 1))
        await _record_receipt(db, budget, amount=0.2, received_at=date(2026, 1, 2))

        balance = await get_ledger_balance_service(db, _valid_user(), budget.id)

        assert balance.donor_balance == Decimal("0.3")
        assert isinstance(balance.donor_balance, Decimal)


@pytest.mark.anyio
class TestReallocationOnEdit:
    async def test_amount_increase_allocates_the_additional_amount(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=550.0, converted_at=date(2026, 1, 2)
        )
        expense = await _make_expense(db, report, budget_line, amount=300.0)

        await update_report_line_service(
            db, _valid_user(), expense.id, ReportLineUpdate(report_id=report.id, amount=500.0)
        )

        allocations = await _allocations_for(db, expense.id)
        assert sum(a.amount_allocated for a in allocations) == pytest.approx(500.0)

    async def test_amount_decrease_frees_capacity_for_the_next_expense(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=550.0, converted_at=date(2026, 1, 2)
        )
        # Fully consumes the only lot.
        expense = await _make_expense(db, report, budget_line, amount=550.0)

        await update_report_line_service(
            db, _valid_user(), expense.id, ReportLineUpdate(report_id=report.id, amount=200.0)
        )
        assert sum(
            a.amount_allocated for a in await _allocations_for(db, expense.id)
        ) == pytest.approx(200.0)

        # The 350 the edit freed up is now available to a new expense.
        second_expense = await _make_expense(db, report, budget_line, amount=350.0)
        assert sum(
            a.amount_allocated for a in await _allocations_for(db, second_expense.id)
        ) == pytest.approx(350.0)


@pytest.mark.anyio
class TestCompensatingRollback:
    async def test_create_report_line_rolled_back_when_allocation_fails(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)

        with patch(
            "app.services.report_line_services.allocate_fifo_service",
            side_effect=RuntimeError("simulated allocation failure"),
        ):
            with pytest.raises(RuntimeError):
                await create_report_line_service(
                    db,
                    _valid_user(),
                    ReportLineCreate(
                        report_id=report.id,
                        budget_line_id=budget_line.id,
                        description="Expense",
                        amount=300.0,
                        expense_date=date(2026, 6, 15),
                    ),
                )

        assert await list_report_lines(db, report_id=report.id) == []

    async def test_update_report_line_amount_reverted_when_reallocation_fails(self, db):
        budget = await _make_budget(db)
        budget_line = await _make_budget_line(db, budget.id)
        report = await _make_report(db, budget.id)
        await _record_conversion(
            db, budget, donor_amount=500.0, local_amount=550.0, converted_at=date(2026, 1, 2)
        )
        expense = await _make_expense(db, report, budget_line, amount=300.0)

        with patch(
            "app.services.report_line_services.allocate_fifo_service",
            side_effect=[RuntimeError("simulated allocation failure"), None],
        ):
            with pytest.raises(RuntimeError):
                await update_report_line_service(
                    db,
                    _valid_user(),
                    expense.id,
                    ReportLineUpdate(report_id=report.id, amount=999.0),
                )

        await db.refresh(expense)
        assert expense.amount == 300.0


@pytest.mark.anyio
class TestFunderCanViewButNotRecord:
    """Currency-ledger-ui: owner and funder can both view the ledger, but
    recording a receipt or conversion stays owner-only."""

    async def test_funder_can_list_receipts_and_conversions_and_read_balance(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID)

        assert await list_funding_receipts_service(db, _valid_user(FUNDER_ID), budget.id) == []
        assert await list_currency_conversions_service(db, _valid_user(FUNDER_ID), budget.id) == []
        balance = await get_ledger_balance_service(db, _valid_user(FUNDER_ID), budget.id)
        assert balance.budget_id == budget.id

    async def test_stranger_cannot_view_the_ledger(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID)

        with pytest.raises(DomainError):
            await list_funding_receipts_service(db, _valid_user(STRANGER_ID), budget.id)

    async def test_funder_cannot_record_a_receipt(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID)

        with pytest.raises(PermissionDenied):
            await record_receipt_service(
                db,
                _valid_user(FUNDER_ID),
                FundingReceiptCreate(
                    budget_id=budget.id, amount=100.0, received_at=date(2026, 1, 5)
                ),
            )

    async def test_funder_cannot_record_a_conversion(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID)

        with pytest.raises(PermissionDenied):
            await record_conversion_service(
                db,
                _valid_user(FUNDER_ID),
                CurrencyConversionCreate(
                    budget_id=budget.id,
                    donor_amount=100.0,
                    local_amount=110.0,
                    converted_at=date(2026, 1, 5),
                ),
            )
