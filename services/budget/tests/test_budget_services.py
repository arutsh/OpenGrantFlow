"""
Tests for budget service layer logic.

P2: populate_budget_with_user_details graceful degradation — when inter-service
    calls (users cache or customers HTTP) raise, the endpoint still returns 200
    with partial nulls instead of propagating a 500.
P3: create_budget_with_lines_service — asserts created budget gets status=ai_draft.
P4: delete_budget_service — an IntegrityError from the crud layer (e.g. a
    budget with existing funding receipts/currency conversions/reports, all
    hard non-cascading FKs to budgets.id) is translated into a clean
    DomainError(400) rather than surfacing as an unhandled 500.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import uuid
from uuid import uuid4

from main import app
from app.api.budget_routes import get_validated_user
from tests.factories.user import make_valid_user
from tests.factories.budget import BudgetFactory, BudgetLineFactory

client = TestClient(app)

USER_ID = str(uuid4())
CUSTOMER_ID = str(uuid4())


def _mock_valid_user():
    return make_valid_user(user_id=USER_ID, customer_id=CUSTOMER_ID)


def _enriched(budget, lines=None):
    """Minimal enriched dict matching what populate_budget_with_user_details returns."""
    return {
        "id": budget.id,
        "name": budget.name,
        "owner": {"id": str(CUSTOMER_ID), "name": "Test NGO", "type": "ngo"},
        "funder": {"name": budget.external_funder_name},
        "trace": {
            "created": {"user": None, "event_date": None},
            "updated": {"user": None, "event_date": None},
        },
        "lines": lines or [],
    }


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_validated_user] = _mock_valid_user
    yield
    app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# P2 — Graceful degradation
# ---------------------------------------------------------------------------


class TestPopulateBudgetGracefulDegradation:
    """
    GET /api/v1/budgets/{id} must return 200 even when the users service or
    customers service raises an exception during the enrichment step.
    """

    def test_returns_200_when_both_services_raise(self):
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            funding_customer_id=None,
            external_funder_name="Smith Foundation",
            created_by=USER_ID,
            updated_by=USER_ID,
        )

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                side_effect=Exception("users service unavailable"),
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                side_effect=Exception("customers service unavailable"),
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(budget.id)
        assert data["owner"] is None

    def test_owner_is_null_when_customers_service_raises(self):
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            funding_customer_id=None,
            external_funder_name="Smith Foundation",
            created_by=USER_ID,
            updated_by=USER_ID,
        )

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                side_effect=ConnectionError("timeout"),
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["owner"] is None
        assert data["funder"]["name"] == "Smith Foundation"

    def test_funder_id_preserved_when_customers_service_raises(self):
        funder_id = uuid4()
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            funding_customer_id=funder_id,
            external_funder_name=None,
            created_by=USER_ID,
            updated_by=USER_ID,
        )

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                side_effect=ConnectionError("timeout"),
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        data = response.json()
        # The customer-name lookup failed, but the budget's own
        # funding_customer_id must still surface as funder.id — otherwise a
        # real funder's Confirm button gets hidden by a frontend check that's
        # stricter than the backend's actual funder-confirm rule.
        assert data["funder"]["id"] == str(funder_id)

    def test_end_date_is_computed_from_start_date_and_duration(self):
        from datetime import date

        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            created_by=USER_ID,
            updated_by=USER_ID,
            start_date=date(2026, 1, 15),
            duration_months=6,
        )

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        # start_date + duration_months, mirroring report_services's own
        # period_end default (relativedelta(months=duration_months)) — the
        # frontend no longer computes this itself.
        assert response.json()["end_date"] == "2026-07-15"

    def test_end_date_is_null_without_a_start_date(self):
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            created_by=USER_ID,
            updated_by=USER_ID,
            start_date=None,
        )

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        assert response.json()["end_date"] is None

    def test_trace_users_are_null_when_users_service_raises(self):
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            created_by=USER_ID,
            updated_by=USER_ID,
        )

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                side_effect=RuntimeError("users service down"),
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["trace"]["created"]["user"] is None
        assert data["trace"]["updated"]["user"] is None

    def test_returns_enriched_data_when_services_succeed(self):
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        users_map = {
            str(USER_ID): {
                "id": str(USER_ID),
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
            }
        }
        customers_map = {
            str(CUSTOMER_ID): {"id": str(CUSTOMER_ID), "name": "Test NGO", "type": "ngo"}
        }

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value=users_map,
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                return_value=customers_map,
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["owner"]["name"] == "Test NGO"
        assert data["trace"]["created"]["user"]["first_name"] == "Alice"

    def test_owner_and_trace_resolve_when_model_ids_are_uuid_objects(self):
        """Regression: uuid.UUID model ids must match the string-keyed users/customers maps."""
        owner_uuid = uuid.UUID(CUSTOMER_ID)
        user_uuid = uuid4()
        budget = BudgetFactory.build(
            owner_id=owner_uuid,
            funding_customer_id=None,
            external_funder_name="Smith Foundation",
            created_by=user_uuid,
            updated_by=user_uuid,
        )
        users_map = {
            str(user_uuid): {
                "id": str(user_uuid),
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
            }
        }
        customers_map = {
            str(owner_uuid): {"id": str(owner_uuid), "name": "Test NGO", "type": "ngo"}
        }

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value=users_map,
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                return_value=customers_map,
            ),
            patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        ):
            response = client.get(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["owner"]["id"] == str(owner_uuid)
        assert data["owner"]["name"] == "Test NGO"
        assert data["trace"]["created"]["user"]["first_name"] == "Alice"


# ---------------------------------------------------------------------------
# P3 — ai_draft status
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "budget_name": "AI-Generated Budget",
    "external_funder_name": "Smith Foundation",
    "duration_months": 12,
    "lines": [
        {"category_name": "Personnel", "description": "2 FTE staff", "amount": 100000.0},
    ],
}


class TestAiDraftBudgetStatus:
    """
    POST /api/v1/budgets/with-lines must create the budget with status=ai_draft.
    Manually created budgets via POST /api/v1/budgets/ default to status=draft.
    """

    def test_with_lines_creates_budget_with_ai_draft_status(self):
        from app.schemas.budget_schema import BudgetStatus

        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            external_funder_name="Smith Foundation",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        line = BudgetLineFactory.build(budget_id=budget.id, created_by=USER_ID)

        with (
            patch("app.services.budget_services.create_budget", return_value=budget) as mock_create,
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value={"Personnel": line.category},
            ),
            patch("app.services.budget_services.bulk_create_budget_lines", return_value=[line]),
            patch("app.services.budget_services.recalculate_budget_total"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_enriched(budget),
            ),
            patch(
                "app.services.budget_services.get_customer_cached",
                new_callable=AsyncMock,
                return_value={"currency": "GBP"},
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 200
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("status") == BudgetStatus.ai_draft

    def test_manual_budget_create_defaults_to_draft(self):
        from app.schemas.budget_schema import BudgetStatus

        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            external_funder_name="Donor Corp",
            created_by=USER_ID,
            updated_by=USER_ID,
        )

        with (
            patch("app.services.budget_services.create_budget", return_value=budget) as mock_create,
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            response = client.post(
                "/api/v1/budgets/",
                json={"name": "Manual Budget", "external_funder_name": "Donor Corp"},
            )

        assert response.status_code == 200
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("status") != BudgetStatus.ai_draft


class TestCreateBudgetFieldsPersist:
    """create_budget_service used to silently drop local_currency,
    actual_currency, start_date, duration_months, total_amount,
    donor_total_amount, and estimated_exchange_rate — create_budget()'s
    signature never accepted them, so every budget silently fell back to
    the model's defaults regardless of what was requested."""

    def test_with_lines_forwards_currency_and_duration(self):
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            external_funder_name="Smith Foundation",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        line = BudgetLineFactory.build(budget_id=budget.id, created_by=USER_ID)
        payload = {**VALID_PAYLOAD, "local_currency": "EUR"}

        with (
            patch("app.services.budget_services.create_budget", return_value=budget) as mock_create,
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value={"Personnel": line.category},
            ),
            patch("app.services.budget_services.bulk_create_budget_lines", return_value=[line]),
            patch("app.services.budget_services.recalculate_budget_total"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_enriched(budget),
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=payload)

        assert response.status_code == 200
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("local_currency") == "EUR"
        assert call_kwargs.get("duration_months") == 12

    def test_manual_create_forwards_currency_and_duration(self):
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            external_funder_name="Donor Corp",
            created_by=USER_ID,
            updated_by=USER_ID,
        )

        with (
            patch("app.services.budget_services.create_budget", return_value=budget) as mock_create,
            patch(
                "app.services.budget_services.get_users_by_ids_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.budget_services.get_customers_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            response = client.post(
                "/api/v1/budgets/",
                json={
                    "name": "Manual Budget",
                    "external_funder_name": "Donor Corp",
                    "local_currency": "NOK",
                    "duration_months": 6,
                },
            )

        assert response.status_code == 200
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("local_currency") == "NOK"
        assert call_kwargs.get("duration_months") == 6

    def test_with_lines_forwards_actual_currency_donor_total_and_exchange_rate(self):
        """Excel-import fields threaded through by budget-export-from-excel
        Group 5 — chat's import_excel.py sets these directly from AI
        extraction (design.md Decision 8)."""
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            external_funder_name="Smith Foundation",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        line = BudgetLineFactory.build(budget_id=budget.id, created_by=USER_ID)
        payload = {
            **VALID_PAYLOAD,
            "local_currency": "AMD",
            "actual_currency": "EUR",
            "donor_total_amount": 100.0,
            "estimated_exchange_rate": 450.0,
        }

        with (
            patch("app.services.budget_services.create_budget", return_value=budget) as mock_create,
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value={"Personnel": line.category},
            ),
            patch("app.services.budget_services.bulk_create_budget_lines", return_value=[line]),
            patch("app.services.budget_services.recalculate_budget_total"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_enriched(budget),
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=payload)

        assert response.status_code == 200
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("actual_currency") == "EUR"
        assert call_kwargs.get("donor_total_amount") == 100.0
        assert call_kwargs.get("estimated_exchange_rate") == 450.0

    def test_with_lines_falls_back_to_org_currency_when_local_currency_missing(self):
        """A null (or low-confidence, already filtered out by chat service)
        local_currency falls back to the owning org's own default currency
        rather than the model's hardcoded 'GBP' column default."""
        budget = BudgetFactory.build(
            owner_id=CUSTOMER_ID,
            external_funder_name="Smith Foundation",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        line = BudgetLineFactory.build(budget_id=budget.id, created_by=USER_ID)

        with (
            patch("app.services.budget_services.create_budget", return_value=budget) as mock_create,
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value={"Personnel": line.category},
            ),
            patch("app.services.budget_services.bulk_create_budget_lines", return_value=[line]),
            patch("app.services.budget_services.recalculate_budget_total"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_enriched(budget),
            ),
            patch(
                "app.services.budget_services.get_customer_cached",
                new_callable=AsyncMock,
                return_value={"currency": "AMD"},
            ) as mock_get_customer,
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 200
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("local_currency") == "AMD"
        mock_get_customer.assert_called_once_with(CUSTOMER_ID)

    def test_with_lines_fails_when_currency_fallback_unreachable(self):
        """A CustomerServiceError while resolving the org's default currency
        propagates as a 500 rather than silently defaulting to GBP."""
        from app.services.customer_client import CustomerServiceError

        with patch(
            "app.services.budget_services.get_customer_cached",
            new_callable=AsyncMock,
            side_effect=CustomerServiceError("unreachable"),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 500


class TestDeleteBudgetIntegrityGuard:
    def test_delete_blocked_by_existing_ledger_rows_returns_domain_error(self):
        budget = BudgetFactory.build(id=uuid4(), owner_id=CUSTOMER_ID)

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_services.delete_budget",
                side_effect=IntegrityError("DELETE", {}, Exception("FK violation")),
            ),
        ):
            response = client.delete(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 400
        assert "cannot be deleted" in response.json()["detail"].lower()

    def test_delete_succeeds_when_no_dependent_rows(self):
        budget = BudgetFactory.build(id=uuid4(), owner_id=CUSTOMER_ID)

        with (
            patch("app.services.budget_services.get_budget", return_value=budget),
            patch("app.services.budget_services.delete_budget", return_value=True),
        ):
            response = client.delete(f"/api/v1/budgets/{budget.id}")

        assert response.status_code == 200
        assert response.json() == {"success": True}
