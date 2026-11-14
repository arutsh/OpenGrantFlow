# /services/budget/app/api/currency_conversion_routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.currency_ledger_schema import (
    CurrencyConversion,
    CurrencyConversionCreate,
    CurrencyConversionUpdate,
    LedgerBalance,
)
from app.services.currency_ledger_services import (
    record_conversion_service,
    get_currency_conversion_service,
    list_currency_conversions_service,
    get_ledger_balance_service,
    update_conversion_service,
    delete_conversion_service,
    reset_ledger_service,
)
from shared.observability import set_span_attributes
from shared.security.dependencies import get_validated_user

router = APIRouter(prefix="/currency-conversions", tags=["Currency Conversions"])


@router.post("/", response_model=CurrencyConversion)
async def create_currency_conversion_view(
    conversion: CurrencyConversionCreate,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(budget_id=conversion.budget_id)
    created_conversion = await record_conversion_service(db, valid_user, conversion)
    set_span_attributes(conversion_id=created_conversion.id)
    return created_conversion


@router.post("/reset/{budget_id}")
async def reset_ledger_view(
    budget_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(budget_id=budget_id)
    return await reset_ledger_service(db, valid_user, budget_id)


@router.get("/balance/{budget_id}", response_model=LedgerBalance)
async def get_ledger_balance_view(
    budget_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(budget_id=budget_id)
    return await get_ledger_balance_service(db, valid_user, budget_id)


@router.get("/{conversion_id}", response_model=CurrencyConversion)
async def get_currency_conversion_view(
    conversion_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(conversion_id=conversion_id)
    return await get_currency_conversion_service(db, valid_user, conversion_id)


@router.patch("/{conversion_id}", response_model=CurrencyConversion)
async def update_currency_conversion_view(
    conversion_id: UUID,
    conversion: CurrencyConversionUpdate,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(conversion_id=conversion_id)
    return await update_conversion_service(db, valid_user, conversion_id, conversion)


@router.delete("/{conversion_id}")
async def delete_currency_conversion_view(
    conversion_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(conversion_id=conversion_id)
    return {"success": await delete_conversion_service(db, valid_user, conversion_id)}


@router.get("/by-budget/{budget_id}", response_model=List[CurrencyConversion])
async def list_currency_conversions_view(
    budget_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(budget_id=budget_id)
    return await list_currency_conversions_service(db, valid_user, budget_id)
