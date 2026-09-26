from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.currency_ledger import FundingReceiptModel
from uuid import UUID


async def create_funding_receipt(
    session: AsyncSession,
    user_id: UUID,
    budget_id: UUID,
    amount: Decimal,
    received_at: date,
) -> FundingReceiptModel:
    receipt = FundingReceiptModel(
        budget_id=budget_id,
        amount=amount,
        received_at=received_at,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(receipt)
    await session.commit()
    return receipt


async def get_funding_receipt(
    session: AsyncSession, receipt_id: UUID
) -> FundingReceiptModel | None:
    result = await session.execute(
        select(FundingReceiptModel).where(FundingReceiptModel.id == receipt_id)
    )
    return result.scalar_one_or_none()


async def list_funding_receipts(
    session: AsyncSession, budget_id: UUID | None = None
) -> list[FundingReceiptModel]:
    query = select(FundingReceiptModel)
    if budget_id:
        query = query.where(FundingReceiptModel.budget_id == budget_id)
    result = await session.execute(query.order_by(FundingReceiptModel.received_at))
    return list(result.scalars().all())
