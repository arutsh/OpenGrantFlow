# /services/budget/app/api/funding_receipt_routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.currency_ledger_schema import (
    FundingReceipt,
    FundingReceiptCreate,
    FundingReceiptUpdate,
)
from app.services.currency_ledger_services import (
    record_receipt_service,
    get_funding_receipt_service,
    list_funding_receipts_service,
    update_receipt_service,
    delete_receipt_service,
)
from shared.observability import set_span_attributes
from shared.security.dependencies import get_validated_user

router = APIRouter(prefix="/funding-receipts", tags=["Funding Receipts"])


@router.post("/", response_model=FundingReceipt)
async def create_funding_receipt_view(
    receipt: FundingReceiptCreate,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(budget_id=receipt.budget_id)
    created_receipt = await record_receipt_service(db, valid_user, receipt)
    set_span_attributes(funding_receipt_id=created_receipt.id)
    return created_receipt


@router.get("/{receipt_id}", response_model=FundingReceipt)
async def get_funding_receipt_view(
    receipt_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(funding_receipt_id=receipt_id)
    return await get_funding_receipt_service(db, valid_user, receipt_id)


@router.patch("/{receipt_id}", response_model=FundingReceipt)
async def update_funding_receipt_view(
    receipt_id: UUID,
    receipt: FundingReceiptUpdate,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(funding_receipt_id=receipt_id)
    return await update_receipt_service(db, valid_user, receipt_id, receipt)


@router.delete("/{receipt_id}")
async def delete_funding_receipt_view(
    receipt_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(funding_receipt_id=receipt_id)
    return {"success": await delete_receipt_service(db, valid_user, receipt_id)}


@router.get("/by-budget/{budget_id}", response_model=List[FundingReceipt])
async def list_funding_receipts_view(
    budget_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(budget_id=budget_id)
    return await list_funding_receipts_service(db, valid_user, budget_id)
