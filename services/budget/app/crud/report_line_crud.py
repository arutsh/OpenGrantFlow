from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.report import ReportLineModel
from uuid import UUID


async def create_report_line(
    session: AsyncSession,
    user_id: UUID,
    report_id: UUID,
    budget_line_id: UUID,
    description: str,
    amount: Decimal,
    expense_date: date,
    extra_fields: dict | None = None,
) -> ReportLineModel:
    report_line = ReportLineModel(
        report_id=report_id,
        budget_line_id=budget_line_id,
        description=description,
        amount=amount,
        expense_date=expense_date,
        extra_fields=extra_fields,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(report_line)
    await session.commit()
    return report_line


async def get_report_line(session: AsyncSession, report_line_id: UUID) -> ReportLineModel | None:
    result = await session.execute(
        select(ReportLineModel).where(ReportLineModel.id == report_line_id)
    )
    return result.scalar_one_or_none()


async def list_report_lines(
    session: AsyncSession, report_id: UUID | None = None
) -> list[ReportLineModel]:
    query = select(ReportLineModel)
    if report_id:
        query = query.where(ReportLineModel.report_id == report_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_report_line(
    session: AsyncSession,
    report_line: ReportLineModel,
    description: str | None = None,
    amount: Decimal | None = None,
    expense_date: date | None = None,
    extra_fields: dict | None = None,
) -> ReportLineModel:
    if description is not None:
        report_line.description = description
    if amount is not None:
        report_line.amount = amount
    if expense_date is not None:
        report_line.expense_date = expense_date
    if extra_fields is not None:
        report_line.extra_fields = {**(report_line.extra_fields or {}), **extra_fields}
    await session.commit()
    return report_line


async def delete_report_line(session: AsyncSession, report_line: ReportLineModel) -> bool:
    await session.delete(report_line)
    await session.commit()
    return True
