# /services/budget/app/models/report.py
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    ForeignKey,
    Numeric,
    Integer,
    JSON,
    Date,
    DateTime,
    Enum as SQLEnum,
    text,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.utils.db import GUID

from app.models.base import Base

from shared.db.audit_mixin import AuditMixin
from typing import TYPE_CHECKING
from app.schemas.report_schema import ReportStatus

if TYPE_CHECKING:
    from app.models.budget import BudgetModel, BudgetLineModel
    from app.models.currency_ledger import ReportLineConversionAllocationModel


class ReportModel(Base, AuditMixin):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        index=True,
        default=lambda: uuid.uuid4(),
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("budgets.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus, name="report_status"),
        nullable=False,
        default=ReportStatus.draft,
        server_default=text(f"'{ReportStatus.draft.value}'"),
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    budget: Mapped["BudgetModel"] = relationship("BudgetModel", back_populates="reports")
    lines: Mapped[list["ReportLineModel"]] = relationship(
        "ReportLineModel",
        back_populates="report",
        foreign_keys="[ReportLineModel.report_id]",
        cascade="all, delete-orphan",
    )


class ReportLineModel(Base, AuditMixin):
    __tablename__ = "report_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, index=True, default=lambda: uuid.uuid4()
    )
    report_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("reports.id"), nullable=False)
    budget_line_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("budget_lines.id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    # The real-world date the expense happened — distinct from AuditMixin's
    # created_at (when the row was written). A receipt entered today for a
    # purchase 10 days ago must record the 10-days-ago date here.
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    extra_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)

    report: Mapped["ReportModel"] = relationship(
        "ReportModel", back_populates="lines", foreign_keys="[ReportLineModel.report_id]"
    )
    budget_line: Mapped["BudgetLineModel"] = relationship(
        "BudgetLineModel", back_populates="report_lines"
    )
    attachments: Mapped[list["AttachmentModel"]] = relationship(
        "AttachmentModel", back_populates="report_line", cascade="all, delete-orphan"
    )
    allocations: Mapped[list["ReportLineConversionAllocationModel"]] = relationship(
        "ReportLineConversionAllocationModel",
        back_populates="report_line",
        cascade="all, delete-orphan",
    )


class AttachmentModel(Base, AuditMixin):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, index=True, default=lambda: uuid.uuid4()
    )
    report_line_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("report_lines.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)

    report_line: Mapped["ReportLineModel"] = relationship(
        "ReportLineModel", back_populates="attachments"
    )
