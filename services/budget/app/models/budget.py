# /services/budget/app/models/budget.py
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    ForeignKey,
    Numeric,
    JSON,
    Integer,
    Date,
    DateTime,
    Enum as SQLEnum,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.utils.db import GUID

from app.models.base import Base

from shared.db.audit_mixin import AuditMixin
from typing import TYPE_CHECKING
from app.schemas.budget_schema import BudgetStatus

if TYPE_CHECKING:
    from app.models.report import ReportModel, ReportLineModel


class BudgetModel(Base, AuditMixin):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        index=True,
        default=lambda: uuid.uuid4(),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    funding_customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    external_funder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    local_currency: Mapped[str | None] = mapped_column(String(3), nullable=False, default="GBP")
    actual_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[BudgetStatus] = mapped_column(
        SQLEnum(BudgetStatus, name="budget_status"),
        nullable=False,
        default=BudgetStatus.draft,
        server_default=text(f"'{BudgetStatus.draft.value}'"),
    )
    donor_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("donor_templates.id"), nullable=True
    )
    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True, default=0, server_default=text("0")
    )
    # Donor's stated commitment (in actual_currency) and the grantee's own
    # planning-time rate estimate — distinct from the currency-ledger's real,
    # bank-derived rate. See budget-report-iteration-2/design.md Decisions 1-4.
    donor_total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    estimated_exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # TODO: this is not correct approach, not a blocker for now
    # but it should be revisited, the imported budget can be modified and if still have to be
    # abl to export it to similar template even if it has more or less lines

    # Set only when this budget was created by a fresh AI-extracted Excel
    # import (no fingerprint match) — the candidate data for an optional
    # "save as reusable template" prompt on confirm. None once a template
    # already matched at import time (donor_template_id already set) or for
    # budgets not created via Excel import at all.
    excel_import_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    excel_import_structure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    excel_import_lines_locked_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lines: Mapped[list["BudgetLineModel"]] = relationship(
        "BudgetLineModel", back_populates="budget"
    )
    reports: Mapped[list["ReportModel"]] = relationship("ReportModel", back_populates="budget")
    categories: Mapped[list["BudgetCategoryModel"]] = relationship(
        "BudgetCategoryModel", back_populates="budget"
    )


class BudgetLineModel(Base, AuditMixin):
    __tablename__ = "budget_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, index=True, default=lambda: uuid.uuid4()
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("budgets.id"), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("budget_categories.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    # store arbitrary metadata (JSON column, default empty dict)
    extra_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)

    budget: Mapped["BudgetModel"] = relationship("BudgetModel", back_populates="lines")
    category: Mapped["BudgetCategoryModel"] = relationship(
        "BudgetCategoryModel", back_populates="lines"
    )
    report_lines: Mapped[list["ReportLineModel"]] = relationship(
        "ReportLineModel", back_populates="budget_line"
    )


class BudgetCategoryModel(Base, AuditMixin):
    __tablename__ = "budget_categories"
    __table_args__ = (UniqueConstraint("budget_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, index=True, default=lambda: uuid.uuid4()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    budget_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    budget: Mapped["BudgetModel"] = relationship("BudgetModel", back_populates="categories")

    lines: Mapped[list["BudgetLineModel"]] = relationship(
        "BudgetLineModel", back_populates="category"
    )
