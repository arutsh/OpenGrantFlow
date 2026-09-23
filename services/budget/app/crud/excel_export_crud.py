from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import BudgetLineModel
from app.models.currency_ledger import CurrencyConversionModel, ReportLineConversionAllocationModel
from app.models.report import ReportLineModel


@dataclass
class AllocationRollup:
    """One report line's expense funded by one currency-conversion lot."""

    amount_allocated: float
    conversion_donor_amount: float
    conversion_local_amount: float


@dataclass
class BudgetLineExpenseRollup:
    """A budget line's total local-currency expenses plus funding allocations."""

    budget_line_id: UUID
    total_local_amount: float
    allocations: list[AllocationRollup] = field(default_factory=list)


async def get_budget_line_expense_rollups(
    session: AsyncSession, budget_id: UUID
) -> dict[UUID, BudgetLineExpenseRollup]:
    """One rollup per budget line of `budget_id`, keyed by budget_line_id."""
    totals_sq = (
        select(
            ReportLineModel.budget_line_id.label("budget_line_id"),
            func.sum(ReportLineModel.amount).label("total_local_amount"),
        )
        .group_by(ReportLineModel.budget_line_id)
        .subquery()
    )
    totals_result = await session.execute(
        select(BudgetLineModel.id, func.coalesce(totals_sq.c.total_local_amount, 0.0))
        .outerjoin(totals_sq, totals_sq.c.budget_line_id == BudgetLineModel.id)
        .where(BudgetLineModel.budget_id == budget_id)
    )
    rollups = {
        line_id: BudgetLineExpenseRollup(budget_line_id=line_id, total_local_amount=total)
        for line_id, total in totals_result.all()
    }
    if not rollups:
        return rollups

    allocations_result = await session.execute(
        select(
            ReportLineModel.budget_line_id,
            ReportLineConversionAllocationModel.amount_allocated,
            CurrencyConversionModel.donor_amount,
            CurrencyConversionModel.local_amount,
        )
        .join(
            ReportLineModel,
            ReportLineModel.id == ReportLineConversionAllocationModel.report_line_id,
        )
        .join(
            CurrencyConversionModel,
            CurrencyConversionModel.id == ReportLineConversionAllocationModel.conversion_id,
        )
        .where(ReportLineModel.budget_line_id.in_(rollups.keys()))
    )
    for budget_line_id, amount_allocated, donor_amount, local_amount in allocations_result.all():
        rollups[budget_line_id].allocations.append(
            AllocationRollup(
                amount_allocated=amount_allocated,
                conversion_donor_amount=donor_amount,
                conversion_local_amount=local_amount,
            )
        )

    return rollups
