from datetime import date

import pytest

from app.crud.excel_export_crud import get_budget_line_expense_rollups
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


async def _seed_conversion(db, budget_id, donor_amount, local_amount):
    return await _persist(
        db,
        CurrencyConversionFactory.build(
            budget_id=budget_id, donor_amount=donor_amount, local_amount=local_amount
        ),
    )


async def _seed_allocation(db, report_line_id, conversion_id, amount_allocated):
    allocation = ReportLineConversionAllocationModel(
        report_line_id=report_line_id,
        conversion_id=conversion_id,
        amount_allocated=amount_allocated,
    )
    return await _persist(db, allocation)


@pytest.mark.anyio
class TestGetBudgetLineExpenseRollups:
    async def test_fully_allocated_line(self, db):
        budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        line = await _seed_budget_line(db, budget.id)
        report_line = await _seed_report_line(db, report.id, line.id, amount=100.0)
        conversion = await _seed_conversion(db, budget.id, donor_amount=50.0, local_amount=100.0)
        await _seed_allocation(db, report_line.id, conversion.id, amount_allocated=100.0)

        rollups = await get_budget_line_expense_rollups(db, budget.id)

        rollup = rollups[line.id]
        assert rollup.total_local_amount == 100.0
        assert len(rollup.allocations) == 1
        assert rollup.allocations[0].amount_allocated == 100.0
        assert rollup.allocations[0].conversion_donor_amount == 50.0
        assert rollup.allocations[0].conversion_local_amount == 100.0

    async def test_partially_allocated_line(self, db):
        budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        line = await _seed_budget_line(db, budget.id)
        report_line = await _seed_report_line(db, report.id, line.id, amount=100.0)
        conversion = await _seed_conversion(db, budget.id, donor_amount=30.0, local_amount=60.0)
        await _seed_allocation(db, report_line.id, conversion.id, amount_allocated=60.0)

        rollups = await get_budget_line_expense_rollups(db, budget.id)

        rollup = rollups[line.id]
        assert rollup.total_local_amount == 100.0
        assert len(rollup.allocations) == 1
        assert rollup.allocations[0].amount_allocated == 60.0

    async def test_zero_expense_line_has_no_allocations(self, db):
        budget = await _seed_budget(db)
        line = await _seed_budget_line(db, budget.id)

        rollups = await get_budget_line_expense_rollups(db, budget.id)

        rollup = rollups[line.id]
        assert rollup.total_local_amount == 0.0
        assert rollup.allocations == []

    async def test_no_budget_lines_returns_empty(self, db):
        budget = await _seed_budget(db)

        rollups = await get_budget_line_expense_rollups(db, budget.id)

        assert rollups == {}

    async def test_multi_lot_allocations_sum_to_full_expense(self, db):
        budget = await _seed_budget(db)
        report = await _seed_report(db, budget.id)
        line = await _seed_budget_line(db, budget.id)
        report_line = await _seed_report_line(db, report.id, line.id, amount=150.0)
        conversion1 = await _seed_conversion(db, budget.id, donor_amount=40.0, local_amount=100.0)
        conversion2 = await _seed_conversion(db, budget.id, donor_amount=20.0, local_amount=50.0)
        await _seed_allocation(db, report_line.id, conversion1.id, amount_allocated=100.0)
        await _seed_allocation(db, report_line.id, conversion2.id, amount_allocated=50.0)

        rollups = await get_budget_line_expense_rollups(db, budget.id)

        rollup = rollups[line.id]
        assert rollup.total_local_amount == 150.0
        assert len(rollup.allocations) == 2
        assert sum(a.amount_allocated for a in rollup.allocations) == 150.0

    async def test_budget_with_unrelated_line_is_not_mixed_in(self, db):
        budget = await _seed_budget(db)
        other_budget = await _seed_budget(db)
        line = await _seed_budget_line(db, budget.id)
        await _seed_budget_line(db, other_budget.id)

        rollups = await get_budget_line_expense_rollups(db, budget.id)

        assert list(rollups.keys()) == [line.id]
