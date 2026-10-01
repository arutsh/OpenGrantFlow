# /services/budget/app/schemas/budget.py

from pydantic import BaseModel, ConfigDict, model_validator
from uuid import UUID
from shared.schemas.budget_line_schema import BudgetLine
from datetime import datetime, date

from enum import Enum
from shared.schemas.money import CalculatedMoney, Money, Rate


class BudgetStatus(str, Enum):
    ai_draft = "ai_draft"
    draft = "draft"
    confirmed = "confirmed"
    archived = "archived"


# Budget Schemass
class BudgetBase(BaseModel):
    name: str | None = None
    owner_id: UUID | None = None
    funding_customer_id: UUID | None = None
    local_currency: str | None = None
    actual_currency: str | None = None
    start_date: date | None = None
    status: BudgetStatus = BudgetStatus.draft
    duration_months: int | None = None
    external_funder_name: str | None = None
    total_amount: Money | None = None
    # Donor's stated commitment (in actual_currency) and the grantee's own
    # planning-time rate estimate, directly entered — never derived. Locked
    # once the budget is confirmed, same as local_currency/actual_currency.
    donor_total_amount: Money | None = None
    estimated_exchange_rate: Rate | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class BudgetCreate(BudgetBase):
    name: str

    @model_validator(mode="after")
    def check_funder(self):
        if not self.funding_customer_id and not self.external_funder_name:
            raise ValueError("Funding source is required")
        return self


class BudgetUpdate(BudgetBase):
    id: UUID | None = None
    # Override BudgetBase's status default: on a PATCH, omitting `status`
    # must mean "leave it unchanged", not silently coerce to `draft` (the
    # value crud.update_budget's `status or budget.status` fallback assumes
    # for "unset"). BudgetBase's default only makes sense for BudgetCreate,
    # where a brand-new budget really does start as a draft.
    status: BudgetStatus | None = None
    # Also the PATCH response shape (response_model=BudgetUpdate) — declared
    # here, same as on Budget/BudgetWithLines, so a confirm/revert or a
    # donor-commitment edit doesn't leave the caller with a stale value until
    # it refetches (see budget_services._budget_update_response).
    confirmed_at: datetime | None = None
    estimated_local_cap: CalculatedMoney | None = None
    # Whether an optional "save as reusable template" prompt should be
    # offered — true only for a fresh AI-extracted Excel import (no
    # fingerprint match) whose lines haven't been edited since creation.
    can_save_as_template: bool = False
    model_config = ConfigDict(from_attributes=True)


class Budget(BudgetBase):
    id: UUID
    # Read-only: set by the server (confirm transition) / derived at read
    # time (donor_total_amount × estimated_exchange_rate) — never accepted
    # from BudgetCreate/BudgetUpdate payloads since they don't inherit these.
    confirmed_at: datetime | None = None
    estimated_local_cap: CalculatedMoney | None = None
    can_save_as_template: bool = False
    lines: list[BudgetLine] = []
    model_config = ConfigDict(from_attributes=True)


class CustomerOut(BaseModel):
    id: UUID | None = None
    name: str | None = None
    is_ngo: bool | None = None
    is_donor: bool | None = None


class UserOut(BaseModel):
    id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


class TraceEvent(BaseModel):
    user: UserOut | None = None
    event_date: datetime | None = None


class TraceOut(BaseModel):
    created: TraceEvent
    updated: TraceEvent


class BudgetWithLines(BaseModel):
    id: UUID
    name: str
    status: BudgetStatus | None = None
    duration_months: int | None = None
    local_currency: str | None = None
    actual_currency: str | None = None
    start_date: date | None = None
    # There is no `end_date` column — it's start_date + duration_months,
    # computed once here (see populate_budget_with_user_details) so the
    # frontend has one source of truth instead of reimplementing the
    # formula (must match report_services.create_report_service's default
    # period_end: budget.start_date + relativedelta(months=duration_months)).
    end_date: date | None = None
    total_amount: Money | None = None
    donor_total_amount: Money | None = None
    estimated_exchange_rate: Rate | None = None
    confirmed_at: datetime | None = None
    estimated_local_cap: CalculatedMoney | None = None
    can_save_as_template: bool = False
    owner: CustomerOut | None = None
    funder: CustomerOut | None = None
    trace: TraceOut | None = None
    lines: list[BudgetLine] = []
    model_config = ConfigDict(from_attributes=True)


class CurrencyAmount(BaseModel):
    currency: str | None = None
    total_allocated: CalculatedMoney


class FundedBudgetsSummary(BaseModel):
    total_budgets: int
    total_allocated_by_currency: list[CurrencyAmount] = []


class GranteeSummary(BaseModel):
    id: UUID | None = None
    name: str | None = None
    country: str | None = None
    budgets_count: int
    total_allocated_by_currency: list[CurrencyAmount] = []


class FundedBudgetListItem(BaseModel):
    id: UUID
    name: str
    status: BudgetStatus
    total_amount: Money | None = None
    local_currency: str | None = None
    actual_currency: str | None = None
    donor_total_amount: Money | None = None
    estimated_exchange_rate: Rate | None = None
    confirmed_at: datetime | None = None
    estimated_local_cap: CalculatedMoney | None = None
    owner: CustomerOut | None = None
    model_config = ConfigDict(from_attributes=True)
