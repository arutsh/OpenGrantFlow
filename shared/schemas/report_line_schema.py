from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import date, datetime
from typing import Any
from shared.schemas.money import Money


class ReportLineBase(BaseModel):
    report_id: UUID | None = None
    budget_line_id: UUID | None = None
    description: str | None = None
    amount: Money | None = None
    # The real-world date the expense happened, not when the row was
    # written (see AuditMixin's created_at for that).
    expense_date: date | None = None
    extra_fields: dict[str, Any] | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class ReportLineCreate(ReportLineBase):
    report_id: UUID
    budget_line_id: UUID
    description: str
    amount: Money
    expense_date: date


class ReportLineUpdate(BaseModel):
    report_id: UUID
    description: str | None = None
    amount: Money | None = None
    expense_date: date | None = None
    extra_fields: dict[str, Any] | None = None


class ReportLine(ReportLineBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
