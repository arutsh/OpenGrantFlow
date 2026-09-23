import asyncio
import structlog
from datetime import date, datetime, timezone
from dateutil.relativedelta import relativedelta
from fastapi import status, HTTPException
from shared.observability import set_span_attributes
from sqlalchemy.exc import IntegrityError
from app.crud.budget_crud import (
    create_budget,
    get_budget,
    update_budget,
    list_budgets,
    delete_budget,
    get_funded_budgets_summary,
    get_funded_grantees,
    recalculate_budget_total,
)
from app.crud.budget_line_crud import bulk_create_budget_lines
from app.services.budget_category_services import get_or_create_categories_by_names_service
from app.crud.dashboard_crud import (
    count_budgets_by_status,
    sum_committed_by_currency,
    sum_received_by_currency,
    sum_converted_by_currency,
    budget_breakdown,
)
from app.core.exceptions import DomainError, PermissionDenied

from app.services.customer_client import (
    validate_customer_can_fund,
    validate_customer_can_own,
    get_customer_cached,
)
from app.services.donor_grantee_client import validate_donor_grantee_relationship
from app.schemas.budget_schema import (
    BudgetCreate,
    BudgetStatus,
    BudgetStatusCount,
    BudgetUpdate,
    CurrencyAmount,
    ConversionProgress,
    BudgetBreakdownRow,
    GranteeDashboardSummary,
)
from app.schemas.report_schema import ReportStatus
from app.schemas.with_lines_schema import CreateBudgetWithLinesRequest
from uuid import UUID

from typing import List
from app.models import BudgetModel
from app.models.mapping import DonorTemplateModel

from app.services.user_client import get_customers_by_ids
from app.services.user_cache import get_users_by_ids_cached

logger = structlog.get_logger(__name__)


async def create_budget_service(
    budget: BudgetCreate,
    valid_user: dict,
    db,
    include_user_datails: bool = False,
    budget_status: BudgetStatus | None = None,
    commit: bool = True,
):

    if budget.funding_customer_id:
        await validate_customer_can_fund(budget.funding_customer_id, raise_domain_error=True)

    owner_id = valid_user.get("customer_id")

    if valid_user["role"] == "superuser":
        if not budget.owner_id:
            raise DomainError(
                "Superuser must specify owner_id (not associated with a customer).",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        # A bare superuser (no impersonation session) must not be able to
        # create a budget under an arbitrary customer_id — mirrors the same
        # check in update_budget_service.
        await validate_customer_can_own(budget.owner_id, raise_domain_error=True)

        owner_id = budget.owner_id

    if budget.funding_customer_id:
        # owner_id is always set by this point: either the caller's own
        # customer_id claim (always present in a valid JWT) or, for a
        # superuser, budget.owner_id (either client-supplied or the
        # FIXME fallback above) — never None in practice.
        assert owner_id is not None
        validate_donor_grantee_relationship(
            budget.funding_customer_id, owner_id, raise_domain_error=True
        )
    new_budget = await create_budget(
        session=db,
        user_id=valid_user["user_id"],
        name=budget.name,
        funding_customer_id=budget.funding_customer_id,
        external_funder_name=budget.external_funder_name,
        owner_id=owner_id,
        status=budget_status,
        local_currency=budget.local_currency,
        actual_currency=budget.actual_currency,
        start_date=budget.start_date,
        duration_months=budget.duration_months,
        total_amount=budget.total_amount,
        donor_total_amount=budget.donor_total_amount,
        estimated_exchange_rate=budget.estimated_exchange_rate,
        load_lines=include_user_datails,
        commit=commit,
    )
    if not include_user_datails:
        return new_budget
    result = await populate_budget_with_user_details([new_budget], valid_user=valid_user)

    return result[0]


def is_budget_locked(budget) -> bool:
    """A confirmed budget's metadata and lines are frozen to keep reported
    figures accurate. Single source of truth for that rule."""
    return budget is not None and budget.status == BudgetStatus.confirmed


def assert_budget_editable(budget, resource: str) -> None:
    """Shared confirmed-budget edit lock for budget_line_services and
    budget_category_services, so the two never drift."""
    if is_budget_locked(budget):
        raise DomainError(
            f"Budget {resource} cannot be changed once the budget is confirmed",
            status.HTTP_400_BAD_REQUEST,
        )


def _is_metadata_edit(budget: BudgetCreate) -> bool:
    """True if the payload touches anything beyond a bare status/start_date
    transition (confirm or revert-to-draft) or a currency-only update — i.e.
    name/duration/local_currency/funder/owner/donor_total_amount/
    estimated_exchange_rate fields. `actual_currency` is
    deliberately excluded: it's the donor-transfer currency the currency-
    ledger UI needs set, and the ledger's "set actual currency" prompt only
    ever appears on an already-confirmed budget (see budget-report-frontend
    tasks.md 6.7), so locking it the same as name/duration would make that
    flow permanently unreachable. A payload that also touches any other
    metadata field alongside actual_currency is still blocked as usual.

    funding_customer_id/donor_total_amount/estimated_exchange_rate are
    checked via model_fields_set, not `is not None` — those three support an
    explicit-null clear (see their _set kwargs on update_budget), and an
    `is not None` check would miss a clear-only payload entirely, letting a
    confirmed budget's funder/commitment be cleared without tripping this
    lock. The rest can't be meaningfully cleared to null in this domain, so
    `is not None` still correctly reflects whether they were touched.
    """
    if budget.model_fields_set & {
        "funding_customer_id",
        "donor_total_amount",
        "estimated_exchange_rate",
    }:
        return True
    return any(
        value is not None
        for value in (
            budget.name,
            budget.duration_months,
            budget.local_currency,
            budget.external_funder_name,
            budget.owner_id,
        )
    )


def _effective_funder_after_update(
    budget: BudgetCreate, existing: BudgetModel
) -> tuple[UUID | None, str | None]:
    """Mirrors update_budget's own funding_customer_id/external_funder_name
    combination rule (funding_customer_id is only replaced/cleared when
    external_funder_name is explicitly sent alongside it — see the crud
    layer) so the either/or check below reflects what would actually persist,
    not just the raw payload."""
    if budget.external_funder_name is not None:
        return budget.funding_customer_id, budget.external_funder_name
    if budget.funding_customer_id is not None:
        return budget.funding_customer_id, existing.external_funder_name
    return existing.funding_customer_id, existing.external_funder_name


async def _resolve_updatable_budget(
    budget_id: UUID,
    valid_user: dict,
    is_confirm_attempt: bool,
    db,
    load_lines: bool = False,
    load_reports: bool = False,
) -> tuple[BudgetModel, bool]:
    """Authorization for PATCH /budgets/{id}. Returns (budget, is_funder_confirm).

    The owner may always act on their own budget (a superuser reaches this
    via an impersonation session's customer_id, same as anyone else). The one
    exception — a matching funder confirming a draft/ai_draft budget (see
    design.md's "Confirm access extends to the matching funder" decision) —
    is resolved here as an explicit authorization branch rather than by
    catching the owner-lookup's not-found error, so both paths are plain
    reads with no exception-driven control flow between them.
    """
    budget = await get_budget(db, budget_id, load_lines=load_lines, load_reports=load_reports)
    if not budget:
        raise DomainError("Budget Not found", status.HTTP_400_BAD_REQUEST)

    customer_id = valid_user.get("customer_id")
    if customer_id and str(budget.owner_id) == str(customer_id):
        return budget, False

    if (
        is_confirm_attempt
        and budget.funding_customer_id
        and customer_id
        and str(budget.funding_customer_id) == str(customer_id)
        and budget.status in (BudgetStatus.draft, BudgetStatus.ai_draft)
    ):
        return budget, True

    raise DomainError(
        "Budget Not found",
        status.HTTP_400_BAD_REQUEST,
    )


async def update_budget_service(budget_id: UUID, budget: BudgetCreate, valid_user: dict, db):

    if budget.funding_customer_id:
        await validate_customer_can_fund(budget.funding_customer_id, raise_domain_error=True)

    # Broader than "a bare confirm with no other fields" — this also covers a
    # confirm bundled with a metadata edit, so both the archived/already-
    # confirmed guard below and the funder-metadata guard after the lookup
    # see the attempt regardless of what else is in the payload.
    is_confirm_attempt = budget.status == BudgetStatus.confirmed

    valid_budget, is_funder_confirm = await _resolve_updatable_budget(
        budget_id, valid_user, is_confirm_attempt, db, load_reports=True
    )

    if is_funder_confirm and _is_metadata_edit(budget):
        raise DomainError(
            "A funder can only confirm a budget, not edit its metadata",
            status.HTTP_400_BAD_REQUEST,
        )

    if is_confirm_attempt and valid_budget.status not in (
        BudgetStatus.draft,
        BudgetStatus.ai_draft,
    ):
        raise DomainError(
            "Only a draft or ai_draft budget can be confirmed",
            status.HTTP_400_BAD_REQUEST,
        )

    is_reverting = (
        valid_budget.status == BudgetStatus.confirmed
        and budget.status == BudgetStatus.draft
        and not _is_metadata_edit(budget)
    )

    if is_budget_locked(valid_budget) and (
        _is_metadata_edit(budget) or budget.start_date is not None
    ):
        raise DomainError(
            "Budget cannot be edited once it is confirmed",
            status.HTTP_400_BAD_REQUEST,
        )

    # No role-based owner-reassignment branch: impersonation issues role="admin", not
    # "superuser", so gating on role here would bypass the impersonation requirement.
    owner_id = None
    if not is_funder_confirm:
        # checks if customer has right to update the budget
        if (budget.owner_id and str(valid_budget.owner_id) != str(budget.owner_id)) or (
            str(valid_user["customer_id"]) != str(valid_budget.owner_id)
        ):
            raise PermissionDenied()

    if budget.funding_customer_id:
        # Checked against the *final* owner (post-reassignment), not
        # valid_budget.owner_id — a superuser changing owner_id and
        # funding_customer_id in the same request must be validated against
        # the new owner, otherwise the gate could be bypassed by reassigning
        # to an unapproved grantee after the check.
        validate_donor_grantee_relationship(
            budget.funding_customer_id, owner_id or valid_budget.owner_id, raise_domain_error=True
        )

    funder_touched = budget.model_fields_set & {"external_funder_name", "funding_customer_id"}
    if funder_touched:
        eff_funding_customer_id, eff_external_funder_name = _effective_funder_after_update(
            budget, valid_budget
        )
        if not eff_funding_customer_id and not eff_external_funder_name:
            raise DomainError(
                "Budget must have either an approved donor or a funder name",
                status.HTTP_400_BAD_REQUEST,
            )

    if budget.status == BudgetStatus.confirmed:
        effective_start_date = budget.start_date or valid_budget.start_date
        if not effective_start_date:
            raise DomainError(
                "start_date must be set before a budget can be confirmed",
                status.HTTP_400_BAD_REQUEST,
            )

    # Set on every confirm transition (is_confirm_attempt is only reachable
    # here from draft/ai_draft, per the guard above) so a later revert +
    # reconfirm always overwrites the prior value, never left stale.
    confirmed_at = datetime.now(timezone.utc) if is_confirm_attempt else None

    # Cleared explicitly on revert — update_budget's "None means don't
    # touch" convention would otherwise leave the prior confirm timestamp on
    # a budget that's back to draft.
    clear_confirmed_at = is_reverting

    if is_reverting:
        non_draft_reports = [r for r in valid_budget.reports if r.status != ReportStatus.draft]
        if non_draft_reports:
            raise DomainError(
                "Cannot revert to draft while the budget has a submitted, approved, "
                "or rejected report",
                status.HTTP_400_BAD_REQUEST,
            )
        # session.delete only — not crud.delete_report, which commits per
        # call. Batching these into the single commit below (alongside the
        # status change) turns the revert into one round trip instead of N,
        # and makes it atomic: if anything below still fails, nothing here
        # is persisted either.
        for report in list(valid_budget.reports):
            await db.delete(report)

    updated_budget = await update_budget(
        session=db,
        budget_id=budget_id,
        name=budget.name,
        status=budget.status,
        duration_months=budget.duration_months,
        local_currency=budget.local_currency,
        actual_currency=budget.actual_currency,
        start_date=budget.start_date,
        owner_id=owner_id,
        funding_customer_id=budget.funding_customer_id,
        external_funder_name=budget.external_funder_name,
        donor_total_amount=budget.donor_total_amount,
        donor_total_amount_set="donor_total_amount" in budget.model_fields_set,
        estimated_exchange_rate=budget.estimated_exchange_rate,
        estimated_exchange_rate_set="estimated_exchange_rate" in budget.model_fields_set,
        confirmed_at=confirmed_at,
        clear_confirmed_at=clear_confirmed_at,
    )
    if not updated_budget:
        return None
    return _budget_update_response(updated_budget)


async def restore_budget_service(budget_id: UUID, valid_user: dict, db):
    """Reverses an archive. Owner-or-superuser only (no funder branch — see
    design.md's "Owner-only authorization" decision), so is_confirm_attempt
    is always False here even though the target may end up `confirmed`.
    """
    valid_budget, _ = await _resolve_updatable_budget(budget_id, valid_user, False, db)

    if valid_budget.status != BudgetStatus.archived:
        raise DomainError(
            "Only an archived budget can be restored",
            status.HTTP_400_BAD_REQUEST,
        )

    restoring_to_confirmed = bool(valid_budget.confirmed_at and valid_budget.start_date)
    target_status = BudgetStatus.confirmed if restoring_to_confirmed else BudgetStatus.draft

    updated_budget = await update_budget(
        session=db,
        budget_id=budget_id,
        status=target_status,
        clear_confirmed_at=not restoring_to_confirmed,
    )
    if not updated_budget:
        return None
    return _budget_update_response(updated_budget)


# TODO check another TODO regarding this tempates
async def save_budget_as_template_service(
    budget_id: UUID, name: str, valid_user: dict, db
) -> DonorTemplateModel:
    """Promotes an unedited Excel-import budget into a reusable DonorTemplateModel."""
    from app.crud.budget_donor_template_crud import create_donor_template

    valid_budget, _ = await _resolve_updatable_budget(
        budget_id, valid_user, False, db, load_lines=True
    )

    if not _can_save_as_template(valid_budget):
        raise DomainError(
            "This budget isn't eligible to be saved as a template — it must have come "
            "from a fresh Excel import with no matched template, with its lines unedited "
            "since creation.",
            status.HTTP_400_BAD_REQUEST,
        )

    template = await create_donor_template(
        db,
        name=name,
        fingerprint=valid_budget.excel_import_fingerprint,
        detected_structure=valid_budget.excel_import_structure,
    )

    if valid_budget.donor_template_id is None:
        valid_budget.donor_template_id = template.id
        await db.commit()

    return template


async def get_budget_service(budget_id, valid_user, db, include_user_details: bool = False):

    customer_id = valid_user.get("customer_id")
    budget = (
        await get_budget(db, budget_id, customer_id, load_lines=include_user_details)
        if customer_id
        else None
    )
    if not budget:
        raise DomainError(
            "Budget Not found",
            status.HTTP_400_BAD_REQUEST,
        )
    if not include_user_details:
        return budget
    result = await populate_budget_with_user_details([budget], valid_user)
    return result[0]


def _can_view_budget(budget: BudgetModel, valid_user: dict) -> bool:
    customer_id = valid_user.get("customer_id")
    if not customer_id:
        return False
    return str(budget.owner_id) == str(customer_id) or str(budget.funding_customer_id) == str(
        customer_id
    )


async def get_viewable_budget_service(
    budget_id, valid_user, db, include_user_details: bool = False
):
    """Like get_budget_service, but a donor who funds this budget (not just its
    owner) can also view it. Used only by the read/detail route — update and
    delete keep the stricter owner-only get_budget_service unchanged."""
    budget = await get_budget(db, budget_id, load_lines=include_user_details)
    if not budget or not _can_view_budget(budget, valid_user):
        raise DomainError(
            "Budget Not found",
            status.HTTP_400_BAD_REQUEST,
        )
    if not include_user_details:
        return budget
    result = await populate_budget_with_user_details([budget], valid_user)
    return result[0]


async def list_budget_service(valid_user, db, include_user_details: bool = False):
    customer_id = valid_user.get("customer_id")
    if not customer_id:
        return []

    budgets = await list_budgets(db, customer_id=customer_id, load_lines=include_user_details)
    if not include_user_details:
        return budgets
    return await populate_budget_with_user_details(budgets=budgets, valid_user=valid_user)


async def get_funded_budgets_summary_service(funding_customer_id: UUID, db) -> dict:
    return await get_funded_budgets_summary(db, funding_customer_id)


async def get_grantee_dashboard_summary_service(
    customer_id: UUID | None, db
) -> GranteeDashboardSummary:
    """Grantee-facing dashboard aggregation (GET /budgets/dashboard/summary).
    Owner-scoped only (no donor/superuser branch — see design.md's "no new
    permission model" non-goal). Currency figures are always grouped by
    currency, never blended (see the mixed-currency-aggregation fix this
    change follows the same rule as)."""
    if not customer_id:
        return GranteeDashboardSummary()

    status_counts = await count_budgets_by_status(db, customer_id)
    committed = await sum_committed_by_currency(db, customer_id)
    received = await sum_received_by_currency(db, customer_id)
    converted = await sum_converted_by_currency(db, customer_id)
    breakdown_rows = await budget_breakdown(db, customer_id)

    received_map = dict(received)
    converted_map = dict(converted)
    currencies = sorted(set(received_map) | set(converted_map))
    conversion_progress = [
        ConversionProgress(
            currency=currency,
            received=received_map.get(currency, 0.0),
            converted=converted_map.get(currency, 0.0),
            percent=(
                (converted_map.get(currency, 0.0) / received_map[currency] * 100)
                if received_map.get(currency)
                else 0.0
            ),
        )
        for currency in currencies
    ]

    return GranteeDashboardSummary(
        budget_counts_by_status=[
            BudgetStatusCount(status=budget_status, count=count)
            for budget_status, count in status_counts
        ],
        committed_by_currency=[
            CurrencyAmount(currency=currency, total_allocated=amount)
            for currency, amount in committed
        ],
        received_by_currency=[
            CurrencyAmount(currency=currency, total_allocated=amount)
            for currency, amount in received
        ],
        conversion_progress_by_currency=conversion_progress,
        budget_breakdown=[
            BudgetBreakdownRow(
                budget_id=budget.id,
                budget_name=budget.name,
                funding_customer_id=budget.funding_customer_id,
                external_funder_name=budget.external_funder_name,
                local_currency=budget.local_currency,
                converted=converted_amount,
                spent=spent_amount,
                remaining=converted_amount - spent_amount,
            )
            for budget, converted_amount, spent_amount in breakdown_rows
        ],
    )


# TODO return in pydantic?
async def get_funded_grantees_service(funding_customer_id: UUID, valid_user: dict, db) -> list:
    grantees = await get_funded_grantees(db, funding_customer_id)
    owner_ids = [g["owner_id"] for g in grantees if g["owner_id"]]
    try:
        customers_map = await get_customers_by_ids(owner_ids, valid_user.get("token", ""))
    except Exception as exc:
        logger.warning("get_funded_grantees_service: customer lookup failed", error=str(exc))
        customers_map = {}
    return [
        {
            "id": g["owner_id"],
            "name": (customers_map.get(g["owner_id"]) or {}).get("name"),
            "country": (customers_map.get(g["owner_id"]) or {}).get("country"),
            "budgets_count": g["budgets_count"],
            "total_allocated_by_currency": g["total_allocated_by_currency"],
        }
        for g in grantees
    ]


async def get_funded_budgets_service(funding_customer_id: UUID, valid_user: dict, db) -> list:
    budgets = await list_budgets(db, funding_customer_id=funding_customer_id, load_lines=True)
    return await populate_budget_with_user_details(budgets=budgets, valid_user=valid_user)


async def delete_budget_service(budget_id: UUID, valid_user: dict, db):
    # fetch valid budget, if user does not have access relevant error will be raised
    valid_budget = await get_budget_service(budget_id=budget_id, valid_user=valid_user, db=db)

    if valid_budget:
        try:
            return await delete_budget(session=db, budget=valid_budget)
        except IntegrityError:
            await db.rollback()
            raise DomainError(
                "Budget cannot be deleted while it has existing reports, funding receipts, "
                "or currency conversions",
                status.HTTP_400_BAD_REQUEST,
            )
    return False


# from shared.observability import traced


# @traced("create_budget_with_lines_service")
async def create_budget_with_lines_service(
    request: CreateBudgetWithLinesRequest,
    valid_user: dict,
    db,
):
    try:
        owner_id = request.owner_id or valid_user.get("customer_id")
        assert owner_id is not None

        local_currency = request.local_currency
        if not local_currency:
            # Fall back to the org's default currency (Decision 8); errors propagate, no silent GBP.
            local_currency = (await get_customer_cached(owner_id)).get("currency")

        # commit=False throughout: budget + categories + lines + total are flushed only,
        # one db.commit() below makes the whole operation atomic (design.md Decision 5).
        new_budget = await create_budget_service(
            BudgetCreate(
                name=request.budget_name,
                external_funder_name=request.external_funder_name,
                owner_id=owner_id,
                duration_months=request.duration_months,
                local_currency=local_currency,
                actual_currency=request.actual_currency,
                donor_total_amount=request.donor_total_amount,
                estimated_exchange_rate=request.estimated_exchange_rate,
            ),
            valid_user,
            db,
            budget_status=BudgetStatus.ai_draft,
            commit=False,
        )
        set_span_attributes(budget_id=new_budget.id)

        categories_by_name = await get_or_create_categories_by_names_service(
            db,
            valid_user,
            budget_id=new_budget.id,
            category_names=[line_input.category_name for line_input in request.lines],
            commit=False,
        )
        category_ids_by_name = {name: category.id for name, category in categories_by_name.items()}
        line_specs = []
        for line_input in request.lines:
            line_specs.append(
                {
                    "category_id": category_ids_by_name[line_input.category_name],
                    "description": line_input.description,
                    "amount": line_input.amount,
                    "extra_fields": line_input.extra_fields,
                }
            )

        created_lines = await bulk_create_budget_lines(
            db, valid_user["user_id"], new_budget.id, line_specs, commit=False
        )
        await recalculate_budget_total(db, new_budget.id, commit=False)

        # Excel-import provenance, set only by chat's import-excel orchestration.
        if any(
            v is not None
            for v in (
                request.donor_template_id,
                request.excel_import_fingerprint,
                request.excel_import_structure,
                request.excel_import_lines_locked_count,
            )
        ):
            new_budget.donor_template_id = request.donor_template_id
            new_budget.excel_import_fingerprint = request.excel_import_fingerprint
            new_budget.excel_import_structure = request.excel_import_structure
            new_budget.excel_import_lines_locked_count = request.excel_import_lines_locked_count

        await db.commit()

        from app.schemas.budget_line_schema import BudgetLine

        enriched = await get_budget_service(
            new_budget.id, valid_user, db, include_user_details=True
        )
        enriched["lines"] = [BudgetLine.model_validate(ln) for ln in created_lines]
        return enriched

    except (HTTPException, DomainError):
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create budget with lines. Changes have been rolled back.",
        ) from e


def _add_duration_months(start_date: date, duration_months: int | None) -> date:
    """Shared with excel_export_service._period_label — keep both in sync."""
    return start_date + relativedelta(months=duration_months or 0)


def _compute_end_date(budget: BudgetModel):
    """Mirrors report_services.create_report_service's default period_end —
    the single source of truth for this formula, so the frontend displays
    end_date from here rather than reimplementing the math."""
    if not budget.start_date:
        return None
    return _add_duration_months(budget.start_date, budget.duration_months)


def _compute_estimated_local_cap(budget: BudgetModel) -> float | None:
    """donor_total_amount × estimated_exchange_rate, derived at read time —
    never persisted (see design.md Decision 2). `null` when either input is
    unset or zero, not just when unset."""
    if not budget.donor_total_amount or not budget.estimated_exchange_rate:
        return None
    return budget.donor_total_amount * budget.estimated_exchange_rate


def _can_save_as_template(budget: BudgetModel) -> bool:
    """True if the budget is a fresh, unmatched Excel import with unedited lines."""
    if budget.excel_import_fingerprint is None or budget.donor_template_id is not None:
        return False
    if len(budget.lines) != budget.excel_import_lines_locked_count:
        return False
    return all(line.updated_at is None for line in budget.lines)


def _budget_update_response(budget: BudgetModel) -> BudgetUpdate:
    """PATCH /budgets/{id} response shape (response_model=BudgetUpdate).

    Unlike Budget/BudgetWithLines — which are always built from an already-
    enriched dict via populate_budget_with_user_details — handing the raw ORM
    object straight to response_model=BudgetUpdate raises a pydantic
    ValidationError (BudgetBase has no `from_attributes` config). Building a
    real BudgetUpdate instance here also lets confirmed_at (a real column,
    but excluded from BudgetBase) and estimated_local_cap (never a column at
    all) round-trip on this response, matching what a follow-up GET would
    return instead of leaving the caller with stale values until it
    refetches.
    """
    return BudgetUpdate(
        id=budget.id,
        name=budget.name,
        owner_id=budget.owner_id,
        funding_customer_id=budget.funding_customer_id,
        local_currency=budget.local_currency,
        actual_currency=budget.actual_currency,
        start_date=budget.start_date,
        status=budget.status,
        duration_months=budget.duration_months,
        external_funder_name=budget.external_funder_name,
        total_amount=budget.total_amount,
        donor_total_amount=budget.donor_total_amount,
        estimated_exchange_rate=budget.estimated_exchange_rate,
        created_by=budget.created_by,
        updated_by=budget.updated_by,
        updated_at=budget.updated_at,
        created_at=budget.created_at,
        confirmed_at=budget.confirmed_at,
        estimated_local_cap=_compute_estimated_local_cap(budget),
        can_save_as_template=_can_save_as_template(budget),
    )


async def populate_budget_with_user_details(budgets: List[BudgetModel], valid_user: dict):
    # can_save_as_template (below) reads .lines — callers must pass load_lines=True upstream.
    # Collect unique user and customer IDs (str: lookup maps below are keyed by string ids)
    user_ids = {str(b.created_by) for b in budgets if b.created_by}
    user_ids |= {str(b.updated_by) for b in budgets if b.updated_by}
    customer_ids = {str(b.funding_customer_id) for b in budgets if b.funding_customer_id}
    customer_ids |= {str(b.owner_id) for b in budgets if b.owner_id}
    user_ids = user_ids if user_ids else set()
    customer_ids = customer_ids if customer_ids else set()
    # Fetch users/customers concurrently (users from cache with fallback, customers from HTTP)
    users_task = asyncio.create_task(
        get_users_by_ids_cached(list(user_ids), valid_user.get("token", ""))
    )
    customers_task = asyncio.create_task(
        get_customers_by_ids(list(customer_ids), valid_user.get("token", ""))
    )
    try:
        users_map, customers_map = await asyncio.gather(users_task, customers_task)
    except Exception:
        users_map, customers_map = {}, {}

    # Merge enriched data
    enriched = [
        {
            "id": b.id,
            "name": b.name,
            "status": b.status,
            "duration_months": b.duration_months,
            "local_currency": b.local_currency,
            "actual_currency": b.actual_currency,
            "start_date": b.start_date,
            "end_date": _compute_end_date(b),
            "total_amount": b.total_amount,
            "donor_total_amount": b.donor_total_amount,
            "estimated_exchange_rate": b.estimated_exchange_rate,
            "confirmed_at": b.confirmed_at,
            "estimated_local_cap": _compute_estimated_local_cap(b),
            "can_save_as_template": _can_save_as_template(b),
            "owner": customers_map.get(str(b.owner_id)),
            # Preserve `id` from the budget's own funding_customer_id even
            # when the customer-name lookup is empty/failed, so a real
            # funder relationship still round-trips to the frontend's
            # isBudgetFunder check regardless of that lookup's health.
            "funder": (
                customers_map.get(str(b.funding_customer_id)) if b.funding_customer_id else None
            )
            or (
                {"id": b.funding_customer_id, "name": b.external_funder_name}
                if b.funding_customer_id
                else {"name": b.external_funder_name}
            ),
            "trace": {
                "created": {
                    "user": users_map.get(str(b.created_by)) if b.created_by else None,
                    "event_date": b.created_at,
                },
                "updated": {
                    "user": users_map.get(str(b.updated_by)) if b.updated_by else None,
                    "event_date": b.updated_at,
                },
            },
        }
        for b in budgets
    ]
    return enriched
