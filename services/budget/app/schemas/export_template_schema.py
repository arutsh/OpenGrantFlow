from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateVisibility(str, Enum):
    private = "private"
    shared_with_grantees = "shared_with_grantees"


class TemplateSource(str, Enum):
    """How a candidate template relates to the requesting viewer (see
    list_candidate_templates)."""

    system = "system"
    own = "own"
    donor = "donor"


class ExportSheet(str, Enum):
    """The fixed, closed set of sheet renderers a template's `sheets` option
    selects among (design.md Decision 12) — never a per-template layout."""

    original_budget = "original_budget"
    dashboard = "dashboard"
    expense_list = "expense_list"


class ExportTemplateOptions(BaseModel):
    """Bounded renderer options (design.md Decision 9); unknown keys rejected."""

    model_config = ConfigDict(extra="forbid")

    sheets: list[ExportSheet] = Field(
        default_factory=lambda: [
            ExportSheet.original_budget,
            ExportSheet.dashboard,
            ExportSheet.expense_list,
        ]
    )
    show_donor_currency_estimate: bool = True
    column_labels: dict[str, str] = Field(default_factory=dict)
    show_audit_footer: bool = True


class ExportTemplateCreate(BaseModel):
    name: str
    visibility: TemplateVisibility = TemplateVisibility.private
    options: ExportTemplateOptions = Field(default_factory=ExportTemplateOptions)


class ExportTemplateUpdate(BaseModel):
    name: str | None = None
    visibility: TemplateVisibility | None = None
    options: ExportTemplateOptions | None = None


class ExportTemplateCandidate(BaseModel):
    """One entry in the `GET /budgets/{budget_id}/export-templates` response."""

    id: UUID
    name: str
    visibility: TemplateVisibility
    version: int
    source: TemplateSource
