from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import date, datetime
from shared.schemas.money import Money


class FundingReceiptBase(BaseModel):
    budget_id: UUID | None = None
    amount: Money | None = None
    received_at: date | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class FundingReceiptCreate(FundingReceiptBase):
    budget_id: UUID
    amount: Money
    received_at: date


class FundingReceiptUpdate(BaseModel):
    amount: Money | None = None
    received_at: date | None = None

    @field_validator("amount", "received_at")
    @classmethod
    def reject_explicit_null(cls, v):
        # Only runs for fields the client sent; omitting a field leaves it unchanged.
        if v is None:
            raise ValueError("must not be null; omit the field to leave it unchanged")
        return v


class FundingReceipt(FundingReceiptBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class CurrencyConversionBase(BaseModel):
    budget_id: UUID | None = None
    donor_amount: Money | None = None
    local_amount: Money | None = None
    converted_at: date | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class CurrencyConversionCreate(CurrencyConversionBase):
    budget_id: UUID
    donor_amount: Money
    local_amount: Money
    converted_at: date


class CurrencyConversion(CurrencyConversionBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class LedgerBalance(BaseModel):
    """Per-currency balances only — never blended into one figure, per
    design.md's "Multi-currency aggregation always groups by currency"
    decision."""

    budget_id: UUID
    actual_currency: str | None
    donor_balance: Money
    local_currency: str | None
    local_balance: Money
