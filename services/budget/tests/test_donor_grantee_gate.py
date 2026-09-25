"""
Tests for ticket #190 (donor-grantee-relationship-backend, group 2): the
budget-service funding gate. Neither create_budget_service nor
update_budget_service may set funding_customer_id unless a donor_grantees
row exists linking that donor to the budget's owner.

Client-level tests mirror test_customer_validation.py's style. The
create/update integration tests patch donor_grantee_client.check_donor_
grantee_relationship (not validate_donor_grantee_relationship) so the real
validation logic runs end to end, matching how test_budget_donor_commitment.py
et al. mock validate_customer_can_fund at the customer_client boundary.
"""
import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from app.core.exceptions import DomainError
from app.schemas.budget_schema import BudgetCreate, BudgetStatus
from app.services.budget_services import create_budget_service, update_budget_service
from app.services.donor_grantee_client import (
    DonorGranteeServiceError,
    check_donor_grantee_relationship,
    validate_donor_grantee_relationship,
)
from tests.factories.budget import BudgetFactory
from tests.factories.user import make_valid_user

DONOR_ID = str(uuid4())
GRANTEE_ID = str(uuid4())
USER_ID = str(uuid4())
DB = object()  # session is never actually used — every crud call is mocked


def _valid_user(**kwargs):
    kwargs.setdefault("customer_id", GRANTEE_ID)
    return make_valid_user(user_id=USER_ID, **kwargs)


def _payload(**kwargs):
    kwargs.setdefault("name", "Grant")
    kwargs.setdefault("funding_customer_id", DONOR_ID)
    return BudgetCreate(**kwargs)


def _fake_response(payload):
    return httpx.Response(200, json=payload, request=httpx.Request("GET", "http://test"))


def _patch_client_get(**kwargs):
    return patch(
        "app.services.donor_grantee_client._client.get", new_callable=AsyncMock, **kwargs
    )


class TestCheckDonorGranteeRelationship:
    def test_relationship_exists_returns_true(self):
        with _patch_client_get(return_value=_fake_response({"exists": True})):
            assert asyncio.run(check_donor_grantee_relationship(DONOR_ID, GRANTEE_ID)) is True

    def test_relationship_missing_returns_false(self):
        with _patch_client_get(return_value=_fake_response({"exists": False})):
            assert asyncio.run(check_donor_grantee_relationship(DONOR_ID, GRANTEE_ID)) is False

    def test_request_failure_raises_service_error(self):
        with _patch_client_get(side_effect=httpx.ConnectError("boom")):
            with pytest.raises(DonorGranteeServiceError):
                asyncio.run(check_donor_grantee_relationship(DONOR_ID, GRANTEE_ID))


class TestValidateDonorGranteeRelationship:
    def test_existing_relationship_passes(self):
        with patch(
            "app.services.donor_grantee_client.check_donor_grantee_relationship",
            return_value=True,
        ):
            asyncio.run(validate_donor_grantee_relationship(DONOR_ID, GRANTEE_ID))  # does not raise

    def test_missing_relationship_raises_value_error(self):
        with patch(
            "app.services.donor_grantee_client.check_donor_grantee_relationship",
            return_value=False,
        ):
            with pytest.raises(ValueError):
                asyncio.run(validate_donor_grantee_relationship(DONOR_ID, GRANTEE_ID))

    def test_missing_relationship_raises_domain_error_when_flagged(self):
        with patch(
            "app.services.donor_grantee_client.check_donor_grantee_relationship",
            return_value=False,
        ):
            with pytest.raises(DomainError):
                asyncio.run(
                    validate_donor_grantee_relationship(
                        DONOR_ID, GRANTEE_ID, raise_domain_error=True
                    )
                )

    def test_service_error_raises_domain_error_when_flagged(self):
        with patch(
            "app.services.donor_grantee_client.check_donor_grantee_relationship",
            side_effect=DonorGranteeServiceError("unreachable"),
        ):
            with pytest.raises(DomainError):
                asyncio.run(
                    validate_donor_grantee_relationship(
                        DONOR_ID, GRANTEE_ID, raise_domain_error=True
                    )
                )


class TestCreateBudgetServiceGate:
    def test_create_rejected_without_approved_relationship(self):
        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.donor_grantee_client.check_donor_grantee_relationship",
                return_value=False,
            ),
            patch("app.services.budget_services.create_budget") as mock_create,
        ):
            with pytest.raises(DomainError):
                asyncio.run(create_budget_service(_payload(), _valid_user(), DB))
        mock_create.assert_not_called()

    def test_create_succeeds_with_approved_relationship(self):
        budget = BudgetFactory.build(owner_id=GRANTEE_ID, funding_customer_id=DONOR_ID)
        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.donor_grantee_client.check_donor_grantee_relationship",
                return_value=True,
            ),
            patch(
                "app.services.budget_services.create_budget", return_value=budget
            ) as mock_create,
        ):
            result = asyncio.run(create_budget_service(_payload(), _valid_user(), DB))

        assert result.id == budget.id
        mock_create.assert_called_once()

    def test_create_without_funder_is_unaffected(self):
        budget = BudgetFactory.build(owner_id=GRANTEE_ID, funding_customer_id=None)
        payload = BudgetCreate(name="Grant", external_funder_name="Smith Foundation")
        with (
            patch(
                "app.services.donor_grantee_client.check_donor_grantee_relationship"
            ) as mock_check,
            patch(
                "app.services.budget_services.create_budget", return_value=budget
            ) as mock_create,
        ):
            result = asyncio.run(create_budget_service(payload, _valid_user(), DB))

        mock_check.assert_not_called()
        mock_create.assert_called_once()
        assert result.id == budget.id


class TestUpdateBudgetServiceGate:
    def test_attaching_funder_rejected_without_approved_relationship(self):
        """The PATCH-bypass scenario: a budget created funder-less, then
        edited to attach a funder, must be gated exactly like create."""
        existing = BudgetFactory.build(
            id=uuid4(),
            owner_id=GRANTEE_ID,
            funding_customer_id=None,
            status=BudgetStatus.draft,
        )
        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.budget_services.get_budget", return_value=existing),
            patch(
                "app.services.donor_grantee_client.check_donor_grantee_relationship",
                return_value=False,
            ),
            patch("app.services.budget_services.update_budget") as mock_update,
        ):
            with pytest.raises(DomainError):
                asyncio.run(update_budget_service(existing.id, _payload(), _valid_user(), DB))
        mock_update.assert_not_called()

    def test_attaching_funder_succeeds_with_approved_relationship(self):
        existing = BudgetFactory.build(
            id=uuid4(),
            owner_id=GRANTEE_ID,
            funding_customer_id=None,
            status=BudgetStatus.draft,
        )
        with (
            patch(
                "app.services.budget_services.validate_customer_can_fund",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.budget_services.get_budget", return_value=existing),
            patch(
                "app.services.donor_grantee_client.check_donor_grantee_relationship",
                return_value=True,
            ),
            patch(
                "app.services.budget_services.update_budget", return_value=existing
            ) as mock_update,
        ):
            result = asyncio.run(update_budget_service(existing.id, _payload(), _valid_user(), DB))

        assert result.id == existing.id
        mock_update.assert_called_once()

    def test_update_without_funding_customer_id_is_unaffected(self):
        existing = BudgetFactory.build(
            id=uuid4(),
            owner_id=GRANTEE_ID,
            funding_customer_id=DONOR_ID,
            status=BudgetStatus.draft,
        )
        payload = BudgetCreate(name="Renamed", external_funder_name="Smith Foundation")
        with (
            patch("app.services.budget_services.get_budget", return_value=existing),
            patch(
                "app.services.donor_grantee_client.check_donor_grantee_relationship"
            ) as mock_check,
            patch(
                "app.services.budget_services.update_budget", return_value=existing
            ) as mock_update,
        ):
            result = asyncio.run(update_budget_service(existing.id, payload, _valid_user(), DB))

        mock_check.assert_not_called()
        mock_update.assert_called_once()
        assert result.id == existing.id
