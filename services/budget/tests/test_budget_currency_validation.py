"""Budget writes reject non-ISO-4217 currency codes; reads keep legacy codes."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.budget_schema import BudgetCreate, BudgetUpdate, BudgetUpdateResponse

BUDGET_ID = str(uuid.uuid4())

REJECTED_REQUESTS = [
    (
        "post",
        "/api/v1/budgets/",
        {"name": "B", "external_funder_name": "F", "local_currency": "XYZ"},
        "app.api.budget_routes.create_budget_service",
        "local_currency",
    ),
    (
        "patch",
        f"/api/v1/budgets/{BUDGET_ID}",
        {"actual_currency": "EURO"},
        "app.api.budget_routes.update_budget_service",
        "actual_currency",
    ),
    (
        "post",
        "/api/v1/budgets/with-lines",
        {
            "budget_name": "B",
            "external_funder_name": "F",
            "actual_currency": "ABC",
            "lines": [{"category_name": "Personnel", "description": "Salary", "amount": 100}],
        },
        "app.api.budget_routes.create_budget_with_lines_service",
        "actual_currency",
    ),
]


@pytest.mark.parametrize("method, url, payload, service, field", REJECTED_REQUESTS)
def test_invalid_currency_is_rejected_and_writes_nothing(
    make_client, method, url, payload, service, field
):
    client = make_client()
    with patch(service, AsyncMock()) as mock_service:
        response = getattr(client, method)(url, json=payload)

    assert response.status_code == 422
    assert field in response.text
    assert "not a valid ISO 4217" in response.text
    mock_service.assert_not_awaited()


def test_lowercase_code_is_stored_uppercase():
    budget = BudgetCreate(name="B", external_funder_name="F", local_currency="kes")
    assert budget.local_currency == "KES"


def test_omitted_or_null_currency_passes():
    assert BudgetUpdate().actual_currency is None
    assert BudgetUpdate(actual_currency=None).actual_currency is None


def test_response_schema_keeps_legacy_invalid_code():
    assert BudgetUpdateResponse(id=BUDGET_ID, local_currency="XYZ").local_currency == "XYZ"


def test_get_budget_with_legacy_invalid_code_still_returned(make_client):
    client = make_client()
    budget = {"id": BUDGET_ID, "name": "Legacy", "local_currency": "XYZ", "actual_currency": "ABC"}
    with (
        patch("app.api.budget_routes.get_viewable_budget_service", AsyncMock(return_value=budget)),
        patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
    ):
        response = client.get(f"/api/v1/budgets/{BUDGET_ID}")

    assert response.status_code == 200
    assert response.json()["local_currency"] == "XYZ"
    assert response.json()["actual_currency"] == "ABC"


@pytest.mark.parametrize("code", ["", "   ", None])
def test_blank_currency_is_treated_as_unset(code):
    budget = BudgetCreate(name="B", external_funder_name="F", local_currency=code)
    assert budget.local_currency is None


def test_padded_code_is_stripped_and_uppercased():
    assert BudgetUpdate(actual_currency=" usd ").actual_currency == "USD"


@pytest.mark.parametrize("code", ["XXX", "XTS", "XAU", "XAG", "XBA"])
def test_non_tender_codes_are_rejected(code):
    with pytest.raises(ValueError):
        BudgetUpdate(actual_currency=code)
