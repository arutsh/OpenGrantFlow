from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.currency_ledger import CurrencyConversionModel, ReportLineConversionAllocationModel
from app.models.report import ReportLineModel, ReportModel


async def create_currency_conversion(
    session: AsyncSession,
    user_id: UUID,
    budget_id: UUID,
    donor_amount: Decimal,
    local_amount: Decimal,
    converted_at: date,
) -> CurrencyConversionModel:
    conversion = CurrencyConversionModel(
        budget_id=budget_id,
        donor_amount=donor_amount,
        local_amount=local_amount,
        converted_at=converted_at,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(conversion)
    await session.commit()
    return conversion


async def get_currency_conversion(
    session: AsyncSession, conversion_id: UUID
) -> CurrencyConversionModel | None:
    result = await session.execute(
        select(CurrencyConversionModel).where(CurrencyConversionModel.id == conversion_id)
    )
    return result.scalar_one_or_none()


async def list_currency_conversions(
    session: AsyncSession, budget_id: UUID | None = None
) -> list[CurrencyConversionModel]:
    query = select(CurrencyConversionModel)
    if budget_id:
        query = query.where(CurrencyConversionModel.budget_id == budget_id)
    result = await session.execute(query.order_by(CurrencyConversionModel.converted_at))
    return list(result.scalars().all())


async def create_allocation(
    session: AsyncSession,
    report_line_id: UUID,
    conversion_id: UUID,
    amount_allocated: Decimal,
) -> ReportLineConversionAllocationModel:
    allocation = ReportLineConversionAllocationModel(
        report_line_id=report_line_id,
        conversion_id=conversion_id,
        amount_allocated=amount_allocated,
    )
    session.add(allocation)
    await session.commit()
    return allocation


async def delete_allocations_for_report_line(session: AsyncSession, report_line_id: UUID) -> None:
    """Clears a report line's existing allocation rows so it can be safely
    re-derived from scratch (see allocate_fifo_service)."""
    await session.execute(
        delete(ReportLineConversionAllocationModel).where(
            ReportLineConversionAllocationModel.report_line_id == report_line_id
        )
    )
    await session.commit()


async def list_unconsumed_lots(
    session: AsyncSession, budget_id: UUID
) -> list[tuple[CurrencyConversionModel, Decimal]]:
    """This budget's currency conversions with remaining (unallocated)
    balance, oldest-converted first — the FIFO order expenses draw down
    against. One grouped-aggregate query, not one sum-query per conversion."""
    allocated = (
        select(
            ReportLineConversionAllocationModel.conversion_id.label("conversion_id"),
            func.sum(ReportLineConversionAllocationModel.amount_allocated).label("allocated"),
        )
        .group_by(ReportLineConversionAllocationModel.conversion_id)
        .subquery()
    )
    remaining = (
        CurrencyConversionModel.local_amount - func.coalesce(allocated.c.allocated, 0)
    ).label("remaining")
    result = await session.execute(
        select(CurrencyConversionModel, remaining)
        .outerjoin(allocated, allocated.c.conversion_id == CurrencyConversionModel.id)
        .where(CurrencyConversionModel.budget_id == budget_id)
        .order_by(CurrencyConversionModel.converted_at, CurrencyConversionModel.created_at)
    )
    rows = result.all()
    return [(conversion, remaining) for conversion, remaining in rows if remaining > 0]


async def sum_report_line_amounts(session: AsyncSession, budget_id: UUID) -> Decimal:
    """Total of every report-line amount for this budget, regardless of
    allocation state — used to compute the ledger's unconsumed
    local-currency balance."""
    total = (
        await session.execute(
            select(func.sum(ReportLineModel.amount))
            .join(ReportModel, ReportLineModel.report_id == ReportModel.id)
            .where(ReportModel.budget_id == budget_id)
        )
    ).scalar()
    return total or Decimal(0)


async def list_unsatisfied_report_lines(
    session: AsyncSession, budget_id: UUID
) -> list[tuple[ReportLineModel, Decimal]]:
    """This budget's report lines whose amount isn't yet fully covered by
    existing allocations, oldest-created first — walked to retroactively
    backfill allocations when a new conversion is recorded (see design.md's
    2026-07-26 amended note). One grouped-aggregate query, not one
    sum-query per report line."""
    allocated = (
        select(
            ReportLineConversionAllocationModel.report_line_id.label("report_line_id"),
            func.sum(ReportLineConversionAllocationModel.amount_allocated).label("allocated"),
        )
        .group_by(ReportLineConversionAllocationModel.report_line_id)
        .subquery()
    )
    remaining = (ReportLineModel.amount - func.coalesce(allocated.c.allocated, 0)).label(
        "remaining"
    )
    result = await session.execute(
        select(ReportLineModel, remaining)
        .join(ReportModel, ReportLineModel.report_id == ReportModel.id)
        .outerjoin(allocated, allocated.c.report_line_id == ReportLineModel.id)
        .where(ReportModel.budget_id == budget_id, ReportLineModel.amount.isnot(None))
        .order_by(ReportLineModel.created_at, ReportLineModel.id)
    )
    rows = result.all()
    return [(line, remaining) for line, remaining in rows if remaining > 0]
