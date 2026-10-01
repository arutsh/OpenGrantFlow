from uuid import UUID

from pydantic import BaseModel

from shared.schemas.budget_schema import BudgetBase  # noqa: F401
from shared.schemas.budget_schema import BudgetCreate  # noqa: F401
from shared.schemas.budget_schema import Budget  # noqa: F401
from shared.schemas.budget_schema import BudgetUpdate  # noqa: F401
from shared.schemas.budget_schema import BudgetWithLines  # noqa: F401
from shared.schemas.budget_schema import BudgetStatus  # noqa: F401
from shared.schemas.budget_schema import CurrencyAmount  # noqa: F401
from shared.schemas.budget_schema import FundedBudgetsSummary  # noqa: F401
from shared.schemas.budget_schema import GranteeSummary  # noqa: F401
from shared.schemas.budget_schema import FundedBudgetListItem  # noqa: F401
from shared.schemas.money import CalculatedMoney, Money


class BudgetStatusCount(BaseModel):
    status: BudgetStatus
    count: int


class ConversionProgress(BaseModel):
    currency: str
    received: CalculatedMoney
    converted: CalculatedMoney
    # 0-100; 0 when nothing has been received yet in this currency, rather
    # than dividing by zero.
    percent: float


class BudgetBreakdownRow(BaseModel):
    budget_id: UUID
    budget_name: str
    funding_customer_id: UUID | None = None
    external_funder_name: str | None = None
    local_currency: str | None = None
    converted: Money
    spent: Money
    remaining: Money


class GranteeDashboardSummary(BaseModel):
    budget_counts_by_status: list[BudgetStatusCount] = []
    committed_by_currency: list[CurrencyAmount] = []
    received_by_currency: list[CurrencyAmount] = []
    conversion_progress_by_currency: list[ConversionProgress] = []
    budget_breakdown: list[BudgetBreakdownRow] = []
