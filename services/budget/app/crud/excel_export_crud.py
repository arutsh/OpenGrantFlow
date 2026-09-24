from datetime import date
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency_ledger import CurrencyConversionModel, ReportLineConversionAllocationModel
from app.models.report import ReportLineModel, ReportModel


@dataclass
class ReportLineAllocationDetail:
    """One allocation (subline) of a report-line expense: its own conversion
    date/amounts, oldest-first (FIFO consumption order)."""

    amount_allocated: float
    converted_at: date
    conversion_donor_amount: float
    conversion_local_amount: float


@dataclass
class ReportLineExpense:
    """One report-line expense with its ordered currency-conversion allocations."""

    report_line_id: UUID
    budget_line_id: UUID
    description: str | None
    amount: float
    expense_date: date
    allocations: list[ReportLineAllocationDetail] = field(default_factory=list)


async def get_report_line_expenses(
    session: AsyncSession, budget_id: UUID
) -> list[ReportLineExpense]:
    """Every report-line expense across all of `budget_id`'s reports, oldest
    expense first, each with its ordered (oldest-first) allocations."""
    lines_result = await session.execute(
        select(
            ReportLineModel.id,
            ReportLineModel.budget_line_id,
            ReportLineModel.description,
            ReportLineModel.amount,
            ReportLineModel.expense_date,
        )
        .join(ReportModel, ReportModel.id == ReportLineModel.report_id)
        .where(ReportModel.budget_id == budget_id)
        .order_by(ReportLineModel.expense_date, ReportLineModel.id)
    )
    expenses: dict[UUID, ReportLineExpense] = {}
    for report_line_id, budget_line_id, description, amount, expense_date in lines_result.all():
        expenses[report_line_id] = ReportLineExpense(
            report_line_id=report_line_id,
            budget_line_id=budget_line_id,
            description=description,
            amount=amount or 0.0,
            expense_date=expense_date,
        )
    if not expenses:
        return []

    allocations_result = await session.execute(
        select(
            ReportLineConversionAllocationModel.report_line_id,
            ReportLineConversionAllocationModel.amount_allocated,
            CurrencyConversionModel.converted_at,
            CurrencyConversionModel.donor_amount,
            CurrencyConversionModel.local_amount,
        )
        .join(
            CurrencyConversionModel,
            CurrencyConversionModel.id == ReportLineConversionAllocationModel.conversion_id,
        )
        .where(ReportLineConversionAllocationModel.report_line_id.in_(expenses.keys()))
        .order_by(CurrencyConversionModel.converted_at, CurrencyConversionModel.id)
    )
    for (
        report_line_id,
        amount_allocated,
        converted_at,
        donor_amount,
        local_amount,
    ) in allocations_result.all():
        expenses[report_line_id].allocations.append(
            ReportLineAllocationDetail(
                amount_allocated=amount_allocated,
                converted_at=converted_at,
                conversion_donor_amount=donor_amount,
                conversion_local_amount=local_amount,
            )
        )

    return list(expenses.values())
