from datetime import date

import pytest

from app.crud.excel_export_crud import get_report_line_expenses
from app.models.budget import BudgetLineModel
from app.models.currency_ledger import ReportLineConversionAllocationModel
from tests.factories.budget import BudgetFactory
from tests.factories.currency_ledger import CurrencyConversionFactory
from tests.factories.report import ReportFactory, ReportLineFactory


async def _persist(db, instance):
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


async def _seed_budget(db):
    return await _persist(db, BudgetFactory.build())


async def _seed_budget_line(db, budget_id):
    # Raw model, not BudgetLineFactory: its .budget/.category SubFactories null the
    # FK at flush when persisted directly (same trap test_excel_export_service.py avoids).
    line = BudgetLineModel(budget_id=budget_id, description="Salaries", amount=1000.0)
    return await _persist(db, line)


async def _seed_report(db, budget_id):
    return await _persist(db, ReportFactory.build(budget_id=budget_id))


async def _seed_report_line(db, report_id, budget_line_id, amount):
    return await _persist(
        db,
        ReportLineFactory.build(
            report_id=report_id,
            budget_line_id=budget_line_id,
            amount=amount,
            expense_date=date(2026, 2, 1),
        ),
    )


async def _seed_conversion(db, budget_id, donor_amount, local_amount, converted_at=None):
    kwargs = {"budget_id": budget_id, "donor_amount": donor_amount, "local_amount": local_amount}
    if converted_at is not None:
        kwargs["converted_at"] = converted_at
    return await _persist(db, CurrencyConversionFactory.build(**kwargs))


async def _seed_allocation(db, report_line_id, conversion_id, amount_allocated):
    allocation = ReportLineConversionAllocationModel(
        report_line_id=report_line_id,
        conversion_id=conversion_id,
        amount_allocated=amount_allocated,
    )
    return await _persist(db, allocation)


@pytest.mark.anyio
class TestGetReportLineExpenses:
    async def test_unallocated_expense_has_no_allocations(self, db):
        budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        line = await _seed_budget_line(db, budget.id)
        report_line = await _seed_report_line(db, report.id, line.id, amount=100.0)

        expenses = await get_report_line_expenses(db, budget.id)

        assert len(expenses) == 1
        expense = expenses[0]
        assert expense.report_line_id == report_line.id
        assert expense.budget_line_id == line.id
        assert expense.amount == 100.0
        assert expense.allocations == []

    async def test_single_lot_expense_has_one_allocation(self, db):
        budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        line = await _seed_budget_line(db, budget.id)
        report_line = await _seed_report_line(db, report.id, line.id, amount=100.0)
        conversion = await _seed_conversion(db, budget.id, donor_amount=50.0, local_amount=100.0)
        await _seed_allocation(db, report_line.id, conversion.id, amount_allocated=100.0)

        expenses = await get_report_line_expenses(db, budget.id)

        assert len(expenses) == 1
        allocations = expenses[0].allocations
        assert len(allocations) == 1
        assert allocations[0].amount_allocated == 100.0
        assert allocations[0].converted_at == conversion.converted_at
        assert allocations[0].conversion_donor_amount == 50.0
        assert allocations[0].conversion_local_amount == 100.0

    async def test_multi_lot_allocations_ordered_oldest_first_and_sum_to_full_amount(self, db):
        budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        line = await _seed_budget_line(db, budget.id)
        report_line = await _seed_report_line(db, report.id, line.id, amount=150.0)
        older = await _seed_conversion(
            db, budget.id, donor_amount=40.0, local_amount=100.0, converted_at=date(2026, 1, 1)
        )
        newer = await _seed_conversion(
            db, budget.id, donor_amount=20.0, local_amount=50.0, converted_at=date(2026, 2, 1)
        )
        # Seeded newer-conversion-first to prove the query orders by converted_at, not insert order.
        await _seed_allocation(db, report_line.id, newer.id, amount_allocated=50.0)
        await _seed_allocation(db, report_line.id, older.id, amount_allocated=100.0)

        expenses = await get_report_line_expenses(db, budget.id)

        allocations = expenses[0].allocations
        assert len(allocations) == 2
        assert allocations[0].conversion_donor_amount == 40.0  # older lot first
        assert allocations[1].conversion_donor_amount == 20.0
        assert sum(a.amount_allocated for a in allocations) == 150.0

    async def test_ordered_by_expense_date(self, db):
        budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        line = await _seed_budget_line(db, budget.id)
        later = await _persist(
            db,
            ReportLineFactory.build(
                report_id=report.id,
                budget_line_id=line.id,
                amount=10.0,
                expense_date=date(2026, 3, 1),
            ),
        )
        earlier = await _persist(
            db,
            ReportLineFactory.build(
                report_id=report.id,
                budget_line_id=line.id,
                amount=20.0,
                expense_date=date(2026, 1, 1),
            ),
        )

        expenses = await get_report_line_expenses(db, budget.id)

        assert [e.report_line_id for e in expenses] == [earlier.id, later.id]

    async def test_no_report_lines_returns_empty(self, db):
        budget = await _seed_budget(db)

        expenses = await get_report_line_expenses(db, budget.id)

        assert expenses == []

    async def test_budget_with_unrelated_report_line_is_not_mixed_in(self, db):
        budget = await _seed_budget(db)
        other_budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        other_report = await _seed_report(db, other_budget.id)
        line = await _seed_budget_line(db, budget.id)
        other_line = await _seed_budget_line(db, other_budget.id)
        report_line = await _seed_report_line(db, report.id, line.id, amount=100.0)
        await _seed_report_line(db, other_report.id, other_line.id, amount=100.0)

        expenses = await get_report_line_expenses(db, budget.id)

        assert [e.report_line_id for e in expenses] == [report_line.id]
