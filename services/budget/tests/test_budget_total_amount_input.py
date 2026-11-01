"""total_amount is server-derived: input schemas reject it, response schemas still carry it."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.budget_schema import BudgetUpdateResponse

BUDGET_ID = str(uuid.uuid4())

REJECTED_REQUESTS = [
    (
        "post",
        "/api/v1/budgets/",
        {"name": "B", "external_funder_name": "F", "total_amount": 100},
        "app.api.budget_routes.create_budget_service",
    ),
    (
        "patch",
        f"/api/v1/budgets/{BUDGET_ID}",
        {"name": "Renamed", "total_amount": 100},
        "app.api.budget_routes.update_budget_service",
    ),
    (
        "post",
        "/api/v1/budgets/with-lines",
        {
            "budget_name": "B",
            "external_funder_name": "F",
            "total_amount": 100,
            "lines": [{"category_name": "Personnel", "description": "Salary", "amount": 100}],
        },
        "app.api.budget_routes.create_budget_with_lines_service",
    ),
]


@pytest.mark.parametrize("method, url, payload, service", REJECTED_REQUESTS)
def test_request_with_total_amount_is_rejected_and_writes_nothing(
    make_client, method, url, payload, service
):
    client = make_client()
    with patch(service, AsyncMock()) as mock_service:
        response = getattr(client, method)(url, json=payload)

    assert response.status_code == 422
    assert "total_amount is derived from budget lines" in response.text
    mock_service.assert_not_awaited()


def test_patch_without_total_amount_is_accepted(make_client):
    client = make_client()
    returned = BudgetUpdateResponse(id=BUDGET_ID, name="Renamed", total_amount=Decimal("1500.5"))
    with patch(
        "app.api.budget_routes.update_budget_service", AsyncMock(return_value=returned)
    ) as mock_update:
        response = client.patch(f"/api/v1/budgets/{BUDGET_ID}", json={"name": "Renamed"})

    assert response.status_code == 200
    assert response.json()["total_amount"] == 1500.5
    mock_update.assert_awaited_once()


def test_create_without_total_amount_is_accepted(make_client):
    client = make_client()
    with patch(
        "app.api.budget_routes.create_budget_service",
        AsyncMock(return_value={"id": BUDGET_ID, "name": "B", "total_amount": 0}),
    ) as mock_create:
        response = client.post("/api/v1/budgets/", json={"name": "B", "external_funder_name": "F"})

    assert response.status_code == 200
    assert response.json()["total_amount"] == 0
    mock_create.assert_awaited_once()
