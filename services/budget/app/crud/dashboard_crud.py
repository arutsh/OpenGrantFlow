from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.budget import BudgetModel, BudgetStatus
from app.models.currency_ledger import CurrencyConversionModel, FundingReceiptModel
from app.models.report import ReportLineModel, ReportModel


def _owned_confirmed_clause(customer_id: UUID) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    """The owner+confirmed filter pair every dashboard aggregate below scopes
    to (count_budgets_by_status is the one exception — it counts every
    status, not just confirmed) — single source of truth so the two
    conditions can't drift apart across functions."""
    return (BudgetModel.owner_id == customer_id, BudgetModel.status == BudgetStatus.confirmed)


async def count_budgets_by_status(
    session: AsyncSession, customer_id: UUID
) -> list[tuple[BudgetStatus, int]]:
    result = await session.execute(
        select(BudgetModel.status, func.count(BudgetModel.id))
        .where(BudgetModel.owner_id == customer_id)
        .group_by(BudgetModel.status)
    )
    return [(status, count) for status, count in result.all()]


async def sum_committed_by_currency(
    session: AsyncSession, customer_id: UUID
) -> list[tuple[str, Decimal]]:
    """Per design.md Decision 8: committed is built lines (total_amount)
    converted back to the donor's currency via the grantee's own estimated
    rate — never the flat donor_total_amount promise, which can overstate
    what's actually allocated. Budgets missing actual_currency or a usable
    (non-null, non-zero) estimated_exchange_rate are excluded entirely
    rather than folded into another currency's total."""
    result = await session.execute(
        select(
            BudgetModel.actual_currency,
            func.sum(
                func.coalesce(BudgetModel.total_amount, 0) / BudgetModel.estimated_exchange_rate
            ),
        )
        .where(
            *_owned_confirmed_clause(customer_id),
            BudgetModel.actual_currency.isnot(None),
            BudgetModel.estimated_exchange_rate.isnot(None),
            BudgetModel.estimated_exchange_rate != 0,
        )
        .group_by(BudgetModel.actual_currency)
    )
    rows = result.all()
    return [(currency, amount or Decimal(0)) for currency, amount in rows]


async def sum_received_by_currency(
    session: AsyncSession, customer_id: UUID
) -> list[tuple[str, Decimal]]:
    result = await session.execute(
        select(
            BudgetModel.actual_currency,
            func.coalesce(func.sum(FundingReceiptModel.amount), 0),
        )
        .join(FundingReceiptModel, FundingReceiptModel.budget_id == BudgetModel.id)
        .where(*_owned_confirmed_clause(customer_id), BudgetModel.actual_currency.isnot(None))
        .group_by(BudgetModel.actual_currency)
    )
    rows = result.all()
    return [(currency, amount) for currency, amount in rows if currency is not None]


async def sum_converted_by_currency(
    session: AsyncSession, customer_id: UUID
) -> list[tuple[str, Decimal]]:
    """Donor-currency side of each conversion (CurrencyConversion.donor_amount),
    grouped the same way as received-by-currency, so the two are directly
    comparable as a conversion-progress percentage."""
    result = await session.execute(
        select(
            BudgetModel.actual_currency,
            func.coalesce(func.sum(CurrencyConversionModel.donor_amount), 0),
        )
        .join(CurrencyConversionModel, CurrencyConversionModel.budget_id == BudgetModel.id)
        .where(*_owned_confirmed_clause(customer_id), BudgetModel.actual_currency.isnot(None))
        .group_by(BudgetModel.actual_currency)
    )
    rows = result.all()
    return [(currency, amount) for currency, amount in rows if currency is not None]


async def budget_breakdown(
    session: AsyncSession, customer_id: UUID
) -> list[tuple[BudgetModel, Decimal, Decimal]]:
    """One row per confirmed budget this customer owns: (budget, converted,
    spent), both in local_currency. Reuses the same building blocks
    get_ledger_balance_service composes (CurrencyConversion.local_amount and
    ReportLine.amount sums) — no new FIFO/allocation logic — but as two
    grouped subqueries joined once across every confirmed budget, instead of
    N per-budget calls. Each subquery is pre-scoped to this customer's own
    confirmed budget ids rather than aggregating every budget in the system
    and filtering afterward."""
    budget_ids = select(BudgetModel.id).where(*_owned_confirmed_clause(customer_id)).subquery()
    converted_sq = (
        select(
            CurrencyConversionModel.budget_id.label("budget_id"),
            func.sum(CurrencyConversionModel.local_amount).label("converted"),
        )
        .where(CurrencyConversionModel.budget_id.in_(select(budget_ids.c.id)))
        .group_by(CurrencyConversionModel.budget_id)
        .subquery()
    )
    spent_sq = (
        select(
            ReportModel.budget_id.label("budget_id"),
            func.sum(ReportLineModel.amount).label("spent"),
        )
        .join(ReportLineModel, ReportLineModel.report_id == ReportModel.id)
        .where(ReportModel.budget_id.in_(select(budget_ids.c.id)))
        .group_by(ReportModel.budget_id)
        .subquery()
    )
    result = await session.execute(
        select(
            BudgetModel,
            func.coalesce(converted_sq.c.converted, 0),
            func.coalesce(spent_sq.c.spent, 0),
        )
        .outerjoin(converted_sq, converted_sq.c.budget_id == BudgetModel.id)
        .outerjoin(spent_sq, spent_sq.c.budget_id == BudgetModel.id)
        .where(*_owned_confirmed_clause(customer_id))
    )
    rows = result.all()
    return [
        (budget, converted or Decimal(0), spent or Decimal(0)) for budget, converted, spent in rows
    ]
