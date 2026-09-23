"""
Tests for ticket #144: Budget.actual_currency / start_date.

Covers: column round-trip (real sqlite session, matching the convention in
test_budget_line_services.py::TestRecalculateBudgetTotalCrud) and the
start_date-before-confirmed guard in update_budget_service (mocked crud
layer, matching this service's existing test convention).
"""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.factories.user import make_valid_user
from tests.factories.budget import BudgetFactory
from app.core.exceptions import DomainError
from app.schemas.budget_schema import BudgetCreate, BudgetStatus
from app.services.budget_services import update_budget_service

USER_ID = str(uuid4())
CUSTOMER_ID = str(uuid4())
DB = object()  # session is never actually used — every crud call is mocked


def _valid_user():
    return make_valid_user(user_id=USER_ID, customer_id=CUSTOMER_ID)


class TestColumnRoundTrip:
    def test_new_columns_persist_and_reload(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.base import Base
        from app.models.budget import BudgetModel

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[BudgetModel.__table__])
        session = sessionmaker(bind=engine)()

        budget = BudgetModel(
            name="Downstream",
            owner_id=uuid4(),
            local_currency="EUR",
            actual_currency="USD",
            start_date=date(2026, 1, 1),
        )
        session.add(budget)
        session.commit()
        session.refresh(budget)

        reloaded = session.query(BudgetModel).filter(BudgetModel.id == budget.id).one()
        assert reloaded.actual_currency == "USD"
        assert reloaded.start_date == date(2026, 1, 1)

    def test_new_columns_default_to_null(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.base import Base
        from app.models.budget import BudgetModel

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[BudgetModel.__table__])
        session = sessionmaker(bind=engine)()

        budget = BudgetModel(name="Plain", owner_id=uuid4())
        session.add(budget)
        session.commit()
        session.refresh(budget)

        assert budget.actual_currency is None
        assert budget.start_date is None


class TestConfirmRequiresStartDate:
    def _payload(self, **kwargs):
        kwargs.setdefault("name", "Grant")
        kwargs.setdefault("funding_customer_id", uuid4())
        return BudgetCreate(**kwargs)

    def test_confirm_without_start_date_anywhere_is_rejected(self):
        existing = BudgetFactory.build(
            id=uuid4(), owner_id=CUSTOMER_ID, status=BudgetStatus.draft, start_date=None
        )
        payload = self._payload(status=BudgetStatus.confirmed)

        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.budget_services.validate_donor_grantee_relationship",
                return_value=None,
            ),
            patch(
                "app.services.budget_services.get_budget",
                return_value=existing,
            ),
        ):
            with pytest.raises((DomainError, HTTPException)):
                import asyncio

                asyncio.run(update_budget_service(existing.id, payload, _valid_user(), DB))

    def test_confirm_with_start_date_already_on_record_is_allowed(self):
        existing = BudgetFactory.build(
            id=uuid4(),
            owner_id=CUSTOMER_ID,
            status=BudgetStatus.draft,
            start_date=date(2026, 1, 1),
        )
        payload = self._payload(status=BudgetStatus.confirmed)

        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.budget_services.validate_donor_grantee_relationship",
                return_value=None,
            ),
            patch(
                "app.services.budget_services.get_budget",
                return_value=existing,
            ),
            patch(
                "app.services.budget_services.update_budget", return_value=existing
            ) as mock_update,
        ):
            import asyncio

            result = asyncio.run(update_budget_service(existing.id, payload, _valid_user(), DB))

        assert result.id == existing.id
        mock_update.assert_called_once()

    def test_confirm_with_start_date_in_payload_is_allowed(self):
        existing = BudgetFactory.build(
            id=uuid4(), owner_id=CUSTOMER_ID, status=BudgetStatus.draft, start_date=None
        )
        payload = self._payload(status=BudgetStatus.confirmed, start_date=date(2026, 2, 1))

        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.budget_services.validate_donor_grantee_relationship",
                return_value=None,
            ),
            patch(
                "app.services.budget_services.get_budget",
                return_value=existing,
            ),
            patch(
                "app.services.budget_services.update_budget", return_value=existing
            ) as mock_update,
        ):
            import asyncio

            result = asyncio.run(update_budget_service(existing.id, payload, _valid_user(), DB))

        assert result.id == existing.id
        mock_update.assert_called_once()
        # confirmed_at (budget-report-iteration-2, ticket #179) is a freshly
        # generated timestamp on every successful confirm — asserted
        # separately from the rest of the static kwargs below.
        call_kwargs = dict(mock_update.call_args.kwargs)
        confirmed_at = call_kwargs.pop("confirmed_at")
        assert confirmed_at is not None
        assert call_kwargs == dict(
            session=DB,
            budget_id=existing.id,
            name=payload.name,
            status=payload.status,
            duration_months=payload.duration_months,
            local_currency=payload.local_currency,
            actual_currency=payload.actual_currency,
            start_date=payload.start_date,
            owner_id=None,
            funding_customer_id=payload.funding_customer_id,
            external_funder_name=payload.external_funder_name,
            donor_total_amount=payload.donor_total_amount,
            donor_total_amount_set=False,
            estimated_exchange_rate=payload.estimated_exchange_rate,
            estimated_exchange_rate_set=False,
            clear_confirmed_at=False,
        )

    def test_non_confirm_update_does_not_require_start_date(self):
        existing = BudgetFactory.build(
            id=uuid4(), owner_id=CUSTOMER_ID, status=BudgetStatus.draft, start_date=None
        )
        payload = self._payload(status=BudgetStatus.draft, name="Renamed")

        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.budget_services.validate_donor_grantee_relationship",
                return_value=None,
            ),
            patch(
                "app.services.budget_services.get_budget",
                return_value=existing,
            ),
            patch(
                "app.services.budget_services.update_budget", return_value=existing
            ) as mock_update,
        ):
            import asyncio

            result = asyncio.run(update_budget_service(existing.id, payload, _valid_user(), DB))

        assert result.id == existing.id
        mock_update.assert_called_once()
