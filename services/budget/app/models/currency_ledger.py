# /services/budget/app/models/currency_ledger.py
from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, Date
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.utils.db import GUID

from app.models.base import Base

from shared.db.audit_mixin import AuditMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.budget import BudgetModel
    from app.models.report import ReportLineModel


class FundingReceiptModel(Base, AuditMixin):
    __tablename__ = "funding_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, index=True, default=lambda: uuid.uuid4()
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("budgets.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_at: Mapped[date] = mapped_column(Date, nullable=False)

    budget: Mapped["BudgetModel"] = relationship("BudgetModel")


class CurrencyConversionModel(Base, AuditMixin):
    __tablename__ = "currency_conversions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, index=True, default=lambda: uuid.uuid4()
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("budgets.id"), nullable=False)
    donor_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    local_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    converted_at: Mapped[date] = mapped_column(Date, nullable=False)

    budget: Mapped["BudgetModel"] = relationship("BudgetModel")
    allocations: Mapped[list["ReportLineConversionAllocationModel"]] = relationship(
        "ReportLineConversionAllocationModel", back_populates="conversion"
    )


class ReportLineConversionAllocationModel(Base, AuditMixin):
    """FIFO lot-split join: how much of a report-line expense was funded by
    a specific currency conversion. A report line straddling two lots gets
    two rows here; a lot backfilled retroactively for an old overspent
    expense also gets a row here (see design.md's 2026-07-26 amended note)."""

    __tablename__ = "report_line_conversion_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, index=True, default=lambda: uuid.uuid4()
    )
    report_line_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("report_lines.id"), nullable=False
    )
    conversion_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("currency_conversions.id"), nullable=False
    )
    amount_allocated: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    report_line: Mapped["ReportLineModel"] = relationship(
        "ReportLineModel", back_populates="allocations"
    )
    conversion: Mapped["CurrencyConversionModel"] = relationship(
        "CurrencyConversionModel", back_populates="allocations"
    )
