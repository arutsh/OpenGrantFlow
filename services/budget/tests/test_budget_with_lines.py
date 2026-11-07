from decimal import Decimal
import pytest
from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from uuid import uuid4

from main import app
from app.api.budget_routes import get_validated_user
from app.models.budget import BudgetModel, BudgetLineModel, BudgetCategoryModel
from app.schemas.with_lines_schema import BudgetLineInput, CreateBudgetWithLinesRequest
from app.services.budget_services import create_budget_with_lines_service
from tests.factories.user import ValidUserFactory
from tests.factories.budget import BudgetLineFactory, BudgetCategoryFactory

client = TestClient(app)

BUDGET_ID = str(uuid4())
USER_ID = str(uuid4())
CUSTOMER_ID = str(uuid4())
LINE_ID_1 = str(uuid4())
LINE_ID_2 = str(uuid4())
CATEGORY_ID = str(uuid4())

VALID_PAYLOAD: dict[str, Any] = {
    "budget_name": "Youth Program 2025",
    "external_funder_name": "Smith Foundation",
    "duration_months": 12,
    "local_currency": "GBP",
    "lines": [
        {"category_name": "Personnel", "description": "2 FTE staff", "amount": 100000.0},
        {"category_name": "Supplies", "description": "Program supplies", "amount": 5000.0},
    ],
}


def _mock_valid_user():
    return ValidUserFactory(user_id=USER_ID, customer_id=CUSTOMER_ID)


def _mock_budget(budget_id=None):
    m = MagicMock()
    m.id = budget_id or BUDGET_ID
    m.name = "Youth Program 2025"
    m.owner_id = CUSTOMER_ID
    m.external_funder_name = "Smith Foundation"
    m.duration_months = 12
    m.funding_customer_id = None
    m.created_by = USER_ID
    m.updated_by = USER_ID
    m.created_at = None
    m.updated_at = None
    m.status = "draft"
    m.local_currency = "GBP"
    m.reports = []
    return m


def _mock_line(line_id, category_name="Personnel"):
    return BudgetLineFactory.build(
        id=line_id,
        budget_id=BUDGET_ID,
        category_id=CATEGORY_ID,
        description="test",
        amount=1000.0,
        category=BudgetCategoryFactory.build(
            id=CATEGORY_ID, name=category_name, code=category_name.upper()
        ),
    )


def _mock_category(name="Personnel"):
    return BudgetCategoryFactory.build(id=CATEGORY_ID, name=name, code=name.upper())


def _mock_categories_by_name(*names):
    return {name: _mock_category(name) for name in names}


def _mock_enriched_budget(lines=None) -> dict:
    return {
        "id": BUDGET_ID,
        "name": "Youth Program 2025",
        "owner": {"id": CUSTOMER_ID, "name": "Test NGO", "type": "ngo"},
        "funder": {"name": "Smith Foundation"},
        "trace": {
            "created": {"user": {"id": USER_ID}, "event_date": None},
            "updated": {"user": {"id": USER_ID}, "event_date": None},
        },
        "lines": lines or [],
    }


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_validated_user] = _mock_valid_user
    yield
    app.dependency_overrides = {}


class TestCreateBudgetWithLinesEndpoint:
    def test_creates_budget_and_all_lines(self):
        mock_budget = _mock_budget()
        mock_lines = [_mock_line(LINE_ID_1, "Personnel"), _mock_line(LINE_ID_2, "Supplies")]

        with (
            patch("app.services.budget_services.create_budget", return_value=mock_budget),
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value=_mock_categories_by_name("Personnel", "Supplies"),
            ),
            patch("app.services.budget_services.bulk_create_budget_lines", return_value=mock_lines),
            patch("app.services.budget_services.reload_total_amount"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_mock_enriched_budget(mock_lines),
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Youth Program 2025"
        assert len(data["lines"]) == 2

    def test_returns_full_budget_with_enriched_details(self):
        mock_budget = _mock_budget()
        mock_line = _mock_line(LINE_ID_1)
        payload = {**VALID_PAYLOAD, "lines": [VALID_PAYLOAD["lines"][0]]}
        with (
            patch("app.services.budget_services.create_budget", return_value=mock_budget),
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value=_mock_categories_by_name("Personnel"),
            ),
            patch(
                "app.services.budget_services.bulk_create_budget_lines", return_value=[mock_line]
            ),
            patch("app.services.budget_services.reload_total_amount"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_mock_enriched_budget([mock_line]),
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "owner" in data
        assert "funder" in data
        assert data["funder"]["name"] == "Smith Foundation"

    def test_requires_authentication(self):
        app.dependency_overrides = {}
        response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)
        assert response.status_code == 401
        app.dependency_overrides[get_validated_user] = _mock_valid_user

    def test_returns_500_if_category_resolution_fails(self):
        """Failures roll back the transaction now, not compensating deletes."""
        mock_budget = _mock_budget()

        with (
            patch("app.services.budget_services.create_budget", return_value=mock_budget),
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                side_effect=Exception("DB error"),
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 500

    def test_returns_500_if_bulk_line_insert_fails(self):
        """The bulk insert is one commit for all lines, so a failure there is
        all-or-nothing — no partially-created lines to roll back individually."""
        mock_budget = _mock_budget()

        with (
            patch("app.services.budget_services.create_budget", return_value=mock_budget),
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value=_mock_categories_by_name("Personnel", "Supplies"),
            ),
            patch(
                "app.services.budget_services.bulk_create_budget_lines",
                side_effect=Exception("DB error"),
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 500

    def test_duration_months_is_optional(self):
        payload = {
            "budget_name": "Simple Budget",
            "external_funder_name": "Donor Corp",
            "local_currency": "GBP",
            "lines": [{"category_name": "Travel", "description": "Transport", "amount": 2000.0}],
        }
        mock_budget = _mock_budget()
        mock_line = _mock_line(LINE_ID_1, "Travel")

        with (
            patch("app.services.budget_services.create_budget", return_value=mock_budget),
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value=_mock_categories_by_name("Travel"),
            ),
            patch(
                "app.services.budget_services.bulk_create_budget_lines", return_value=[mock_line]
            ),
            patch("app.services.budget_services.reload_total_amount"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_mock_enriched_budget([mock_line]),
            ),
        ):
            response = client.post("/api/v1/budgets/with-lines", json=payload)

        assert response.status_code == 200

    def test_rejects_payload_missing_budget_name(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "budget_name"}
        response = client.post("/api/v1/budgets/with-lines", json=payload)
        assert response.status_code == 422

    def test_rejects_payload_missing_funder_name(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "external_funder_name"}
        response = client.post("/api/v1/budgets/with-lines", json=payload)
        assert response.status_code == 422

    def test_sets_budget_id_span_attribute_on_success(self):
        mock_budget = _mock_budget()
        mock_lines = [_mock_line(LINE_ID_1, "Personnel"), _mock_line(LINE_ID_2, "Supplies")]

        with (
            patch("app.services.budget_services.create_budget", return_value=mock_budget),
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value=_mock_categories_by_name("Personnel", "Supplies"),
            ),
            patch("app.services.budget_services.bulk_create_budget_lines", return_value=mock_lines),
            patch("app.services.budget_services.reload_total_amount"),
            patch(
                "app.services.budget_services.get_budget_service",
                new_callable=AsyncMock,
                return_value=_mock_enriched_budget(mock_lines),
            ),
            patch("app.services.budget_services.set_span_attributes") as mock_set_span_attrs,
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 200
        mock_set_span_attrs.assert_any_call(budget_id=mock_budget.id)

    def test_does_not_set_budget_id_when_budget_creation_fails(self):
        with (
            patch(
                "app.services.budget_services.create_budget",
                side_effect=Exception("DB error creating budget"),
            ),
            patch("app.services.budget_services.set_span_attributes") as mock_set_span_attrs,
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 500
        mock_set_span_attrs.assert_not_called()

    def test_sets_budget_id_when_failure_occurs_after_budget_created(self):
        mock_budget = _mock_budget()

        with (
            patch("app.services.budget_services.create_budget", return_value=mock_budget),
            patch(
                "app.services.budget_services.get_or_create_categories_by_names_service",
                return_value=_mock_categories_by_name("Personnel", "Supplies"),
            ),
            patch(
                "app.services.budget_services.bulk_create_budget_lines",
                side_effect=Exception("DB error"),
            ),
            patch("app.services.budget_services.set_span_attributes") as mock_set_span_attrs,
        ):
            response = client.post("/api/v1/budgets/with-lines", json=VALID_PAYLOAD)

        assert response.status_code == 500
        mock_set_span_attrs.assert_any_call(budget_id=mock_budget.id)


@pytest.mark.anyio
class TestCreateBudgetWithLinesAtomicity:
    """Real-DB (not mocked crud) proof of design.md Decision 5's atomic-write requirement."""

    async def test_success_commits_exactly_once(self, db):
        user = ValidUserFactory()
        request = CreateBudgetWithLinesRequest(
            budget_name="Atomic Budget",
            external_funder_name="Acme Foundation",
            local_currency="GBP",
            lines=[
                BudgetLineInput(category_name="Personnel", description="Staff", amount=1000.0),
                BudgetLineInput(category_name="Supplies", description="Kits", amount=200.0),
            ],
        )

        with patch.object(db, "commit", wraps=db.commit) as mock_commit:
            result = await create_budget_with_lines_service(request, user, db)

        assert mock_commit.await_count == 1
        assert len(result["lines"]) == 2
        assert result["total_amount"] == Decimal("1200")

    async def test_failure_after_lines_flushed_commits_nothing(self, db):
        user = ValidUserFactory()
        request = CreateBudgetWithLinesRequest(
            budget_name="Doomed Budget",
            external_funder_name="Acme Foundation",
            local_currency="GBP",
            lines=[
                BudgetLineInput(category_name="Personnel", description="Staff", amount=1000.0),
            ],
        )

        failure = RuntimeError("simulated failure after budget/category/line flush")
        with patch.object(db, "commit", side_effect=failure):
            with pytest.raises(HTTPException):
                await create_budget_with_lines_service(request, user, db)

        assert (await db.execute(select(BudgetModel))).scalars().all() == []
        assert (await db.execute(select(BudgetLineModel))).scalars().all() == []
        assert (await db.execute(select(BudgetCategoryModel))).scalars().all() == []
