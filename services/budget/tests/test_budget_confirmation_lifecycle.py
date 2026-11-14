"""
Tests for ticket #160's expanded scope (see openspec/changes/budget-report-frontend
design.md's "Confirm access extends to the matching funder" /
"Reverting a confirmed budget to draft" / "Editing budget metadata/lines is
blocked once the budget has any report" decisions).

Uses the shared `db` fixture (conftest.py) — a real sqlite session covering
Budget/BudgetLine/BudgetCategory/Report/ReportLine — since these behaviors
hinge on the real Budget<->Report relationship rather than a single mocked
crud call.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import DomainError
from app.models.budget import BudgetModel, BudgetLineModel, BudgetCategoryModel
from app.models.currency_ledger import FundingReceiptModel
from app.models.report import ReportModel, ReportLineModel
from app.schemas.budget_schema import BudgetStatus, BudgetUpdate
from app.schemas.report_schema import ReportStatus
from app.services.budget_services import update_budget_service
from app.services.budget_line_services import (
    create_budget_line_service,
    update_budget_line_service,
    delete_budget_line_service,
)
from app.schemas import BudgetLineCreate, BudgetLineUpdate
from tests.factories.currency_ledger import CurrencyConversionFactory, FundingReceiptFactory
from tests.factories.user import make_valid_user

OWNER_ID = str(uuid4())
FUNDER_ID = str(uuid4())
STRANGER_ID = str(uuid4())


def _valid_user(customer_id):
    return make_valid_user(customer_id=customer_id)


async def _make_budget(
    db,
    owner_id=OWNER_ID,
    funding_customer_id=None,
    status=BudgetStatus.draft,
    start_date=None,
    duration_months=12,
):
    budget = BudgetModel(
        name="Test Budget",
        owner_id=owner_id,
        funding_customer_id=funding_customer_id,
        status=status,
        start_date=start_date,
        duration_months=duration_months,
        local_currency="GBP",
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


async def _make_report(db, budget_id, status=ReportStatus.draft):
    report = ReportModel(
        budget_id=budget_id,
        name="Interim report",
        status=status,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def _make_receipt(db, budget_id):
    receipt = FundingReceiptFactory.build(budget_id=budget_id)
    db.add(receipt)
    await db.commit()
    return receipt


async def _make_conversion(db, budget_id):
    conversion = CurrencyConversionFactory.build(budget_id=budget_id)
    db.add(conversion)
    await db.commit()
    return conversion


@pytest.mark.anyio
class TestFunderCanConfirm:
    async def test_matching_funder_can_confirm_a_draft_budget(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID, status=BudgetStatus.draft)
        payload = BudgetUpdate(status=BudgetStatus.confirmed, start_date=date(2026, 2, 1))

        result = await update_budget_service(budget.id, payload, _valid_user(FUNDER_ID), db)

        assert result.status == BudgetStatus.confirmed
        assert result.start_date == date(2026, 2, 1)

    async def test_matching_funder_can_confirm_an_ai_draft_budget(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID, status=BudgetStatus.ai_draft)
        payload = BudgetUpdate(status=BudgetStatus.confirmed, start_date=date(2026, 2, 1))

        result = await update_budget_service(budget.id, payload, _valid_user(FUNDER_ID), db)

        assert result.status == BudgetStatus.confirmed

    async def test_stranger_cannot_confirm(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID, status=BudgetStatus.draft)
        payload = BudgetUpdate(status=BudgetStatus.confirmed, start_date=date(2026, 2, 1))

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(STRANGER_ID), db)

    async def test_funder_cannot_edit_metadata(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID, status=BudgetStatus.draft)
        payload = BudgetUpdate(name="Renamed by funder")

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(FUNDER_ID), db)

    async def test_funder_cannot_bundle_a_confirm_with_a_metadata_edit(self, db):
        budget = await _make_budget(db, funding_customer_id=FUNDER_ID, status=BudgetStatus.draft)
        payload = BudgetUpdate(
            status=BudgetStatus.confirmed,
            start_date=date(2026, 2, 1),
            name="Renamed while confirming",
        )

        with pytest.raises(DomainError, match="metadata"):
            await update_budget_service(budget.id, payload, _valid_user(FUNDER_ID), db)

        await db.refresh(budget)
        assert budget.status == BudgetStatus.draft

    async def test_funder_cannot_revert_a_confirmed_budget(self, db):
        budget = await _make_budget(
            db,
            funding_customer_id=FUNDER_ID,
            status=BudgetStatus.confirmed,
            start_date=date(2026, 1, 1),
        )
        payload = BudgetUpdate(status=BudgetStatus.draft)

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(FUNDER_ID), db)


@pytest.mark.anyio
class TestRevertToDraft:
    async def test_owner_can_revert_a_confirmed_budget_with_no_reports(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        payload = BudgetUpdate(status=BudgetStatus.draft)

        result = await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        assert result.status == BudgetStatus.draft

    async def test_revert_clears_confirmed_at(self, db):
        # Leaving a stale confirm timestamp behind would misrepresent history.
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        budget.confirmed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        await db.commit()
        payload = BudgetUpdate(status=BudgetStatus.draft)

        result = await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        assert result.confirmed_at is None
        await db.refresh(budget)
        assert budget.confirmed_at is None

    async def test_revert_blocked_by_a_submitted_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_report(db, budget.id, status=ReportStatus.submitted)
        payload = BudgetUpdate(status=BudgetStatus.draft)

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        await db.refresh(budget)
        assert budget.status == BudgetStatus.confirmed

    async def test_revert_blocked_by_an_approved_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_report(db, budget.id, status=ReportStatus.approved)
        payload = BudgetUpdate(status=BudgetStatus.draft)

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

    async def test_revert_succeeds_and_deletes_draft_reports(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        report = await _make_report(db, budget.id, status=ReportStatus.draft)
        report_id = report.id
        payload = BudgetUpdate(status=BudgetStatus.draft)

        result = await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        assert result.status == BudgetStatus.draft
        remaining = (
            (await db.execute(select(ReportModel).where(ReportModel.budget_id == budget.id)))
            .scalars()
            .all()
        )
        assert remaining == []
        deleted = (
            await db.execute(select(ReportModel).where(ReportModel.id == report_id))
        ).scalar_one_or_none()
        assert deleted is None

    async def test_revert_succeeds_and_deletes_draft_report_with_lines(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        budget_line = BudgetLineModel(budget_id=budget.id, description="Line", amount=100)
        db.add(budget_line)
        await db.commit()
        await db.refresh(budget_line)

        report = await _make_report(db, budget.id, status=ReportStatus.draft)
        report_line = ReportLineModel(
            report_id=report.id,
            budget_line_id=budget_line.id,
            description="Spent",
            amount=50,
            expense_date=date(2026, 6, 15),
        )
        db.add(report_line)
        await db.commit()
        report_id = report.id
        report_line_id = report_line.id

        payload = BudgetUpdate(status=BudgetStatus.draft)

        result = await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        assert result.status == BudgetStatus.draft
        deleted_report = (
            await db.execute(select(ReportModel).where(ReportModel.id == report_id))
        ).scalar_one_or_none()
        deleted_line = (
            await db.execute(select(ReportLineModel).where(ReportLineModel.id == report_line_id))
        ).scalar_one_or_none()
        assert deleted_report is None
        assert deleted_line is None

    async def test_revert_blocked_by_a_funding_receipt(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_receipt(db, budget.id)
        payload = BudgetUpdate(status=BudgetStatus.draft)

        with pytest.raises(DomainError, match="currency ledger"):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        await db.refresh(budget)
        assert budget.status == BudgetStatus.confirmed

    async def test_revert_blocked_by_a_currency_conversion(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_conversion(db, budget.id)
        payload = BudgetUpdate(status=BudgetStatus.draft)

        with pytest.raises(DomainError, match="currency ledger"):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        await db.refresh(budget)
        assert budget.status == BudgetStatus.confirmed

    async def test_revert_blocked_by_non_draft_report_and_ledger_movement(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_report(db, budget.id, status=ReportStatus.submitted)
        await _make_receipt(db, budget.id)
        await _make_conversion(db, budget.id)
        payload = BudgetUpdate(status=BudgetStatus.draft)

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        await db.refresh(budget)
        assert budget.status == BudgetStatus.confirmed
        assert (await db.execute(select(FundingReceiptModel))).scalars().all() != []

    async def test_revert_succeeds_with_empty_ledger_and_draft_reports(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_report(db, budget.id, status=ReportStatus.draft)
        other = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_receipt(db, other.id)
        payload = BudgetUpdate(status=BudgetStatus.draft)

        result = await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        assert result.status == BudgetStatus.draft


@pytest.mark.anyio
class TestConfirmStatusGuard:
    async def test_owner_cannot_reconfirm_an_already_confirmed_budget(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        payload = BudgetUpdate(status=BudgetStatus.confirmed, start_date=date(2026, 2, 1))

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        await db.refresh(budget)
        assert budget.start_date == date(2026, 1, 1)

    async def test_owner_cannot_confirm_an_archived_budget(self, db):
        budget = await _make_budget(db, status=BudgetStatus.archived)
        payload = BudgetUpdate(status=BudgetStatus.confirmed, start_date=date(2026, 2, 1))

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)


@pytest.mark.anyio
class TestStartDateLockedOnceConfirmed:
    async def test_bare_start_date_edit_is_rejected_on_a_confirmed_budget(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        payload = BudgetUpdate(start_date=date(2027, 1, 1))

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        await db.refresh(budget)
        assert budget.start_date == date(2026, 1, 1)


@pytest.mark.anyio
class TestEditLockedOnceConfirmed:
    """Budget metadata/lines lock as soon as the budget is `confirmed` — not
    only once a report exists (a report can only be created against an
    already-confirmed budget, so "confirmed" is strictly broader)."""

    async def test_metadata_edit_blocked_when_confirmed_even_without_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        payload = BudgetUpdate(name="Renamed")

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

    async def test_metadata_edit_blocked_when_confirmed_with_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_report(db, budget.id, status=ReportStatus.draft)
        payload = BudgetUpdate(name="Renamed")

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

    async def test_metadata_edit_allowed_on_a_draft_budget(self, db):
        budget = await _make_budget(db, status=BudgetStatus.draft)
        payload = BudgetUpdate(name="Renamed")

        result = await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        assert result.name == "Renamed"
        # A bare metadata edit that omits `status` must not silently reset it.
        assert result.status == BudgetStatus.draft

    async def test_actual_currency_can_be_set_on_a_confirmed_budget(self, db):
        # actual_currency is deliberately excluded from the metadata lock.
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        payload = BudgetUpdate(actual_currency="USD")

        result = await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

        assert result.actual_currency == "USD"
        assert result.status == BudgetStatus.confirmed

    async def test_actual_currency_alongside_another_metadata_field_still_blocked(self, db):
        # The carve-out is currency-only: bundling with a locked field must not smuggle it through.
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        payload = BudgetUpdate(actual_currency="USD", name="Renamed")

        with pytest.raises(DomainError):
            await update_budget_service(budget.id, payload, _valid_user(OWNER_ID), db)

    async def test_create_budget_line_blocked_when_confirmed_even_without_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        payload = BudgetLineCreate(
            budget_id=budget.id,
            description="New line",
            amount=100.0,
            category_name="Personnel",
        )

        with pytest.raises(DomainError):
            await create_budget_line_service(db, _valid_user(OWNER_ID), payload)

    async def test_create_budget_line_blocked_when_confirmed_with_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        await _make_report(db, budget.id, status=ReportStatus.draft)
        payload = BudgetLineCreate(
            budget_id=budget.id,
            description="New line",
            amount=100.0,
            category_name="Personnel",
        )

        with pytest.raises(DomainError):
            await create_budget_line_service(db, _valid_user(OWNER_ID), payload)

    async def _make_line(self, db, budget_id):
        category = BudgetCategoryModel(name="Personnel", code="PERSONNEL", budget_id=budget_id)
        db.add(category)
        await db.commit()
        await db.refresh(category)
        line = BudgetLineModel(
            budget_id=budget_id, category_id=category.id, description="Line", amount=100.0
        )
        db.add(line)
        await db.commit()
        await db.refresh(line)
        return line

    async def test_update_budget_line_blocked_when_confirmed_even_without_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        line = await self._make_line(db, budget.id)

        with pytest.raises(DomainError):
            await update_budget_line_service(
                db,
                _valid_user(OWNER_ID),
                line.id,
                BudgetLineUpdate(budget_id=budget.id, amount=200.0),
            )

    async def test_update_budget_line_blocked_when_confirmed_with_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        line = await self._make_line(db, budget.id)
        await _make_report(db, budget.id, status=ReportStatus.draft)

        with pytest.raises(DomainError):
            await update_budget_line_service(
                db,
                _valid_user(OWNER_ID),
                line.id,
                BudgetLineUpdate(budget_id=budget.id, amount=200.0),
            )

    async def test_delete_budget_line_blocked_when_confirmed_even_without_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        line = await self._make_line(db, budget.id)

        with pytest.raises(DomainError):
            await delete_budget_line_service(line.id, _valid_user(OWNER_ID), db)

    async def test_delete_budget_line_blocked_when_confirmed_with_a_report(self, db):
        budget = await _make_budget(db, status=BudgetStatus.confirmed, start_date=date(2026, 1, 1))
        line = await self._make_line(db, budget.id)
        await _make_report(db, budget.id, status=ReportStatus.draft)

        with pytest.raises(DomainError):
            await delete_budget_line_service(line.id, _valid_user(OWNER_ID), db)
