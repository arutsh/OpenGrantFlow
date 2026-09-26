import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.exceptions import DomainError
from shared.security.dependencies import get_validated_user

client = TestClient(app)

CUSTOMER_ID = str(uuid.uuid4())
VALID_USER = {
    "user_id": str(uuid.uuid4()),
    "customer_id": CUSTOMER_ID,
    "role": "user",
    "token": "testtoken",
}


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_validated_user] = lambda: VALID_USER
    yield
    app.dependency_overrides = {}


def test_create_budget_endpoint():
    budget_id = str(uuid.uuid4())
    payload = {"name": "Test Budget", "external_funder_name": "name123"}

    with patch(
        "app.api.budget_routes.create_budget_service",
        AsyncMock(return_value={"id": budget_id, "name": "Test Budget"}),
    ) as mock_create:
        response = client.post("/api/v1/budgets/", json=payload)

    assert response.status_code == 200
    assert response.json()["name"] == "Test Budget"
    mock_create.assert_awaited_once()


def test_get_budget_endpoint_found():
    budget_id = str(uuid.uuid4())

    with (
        patch(
            "app.api.budget_routes.get_viewable_budget_service",
            AsyncMock(return_value={"id": budget_id, "name": "Test Budget"}),
        ),
        patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
    ):
        response = client.get(f"/api/v1/budgets/{budget_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Test Budget"
    assert body["lines"] == []


def test_get_budget_endpoint_money_fields_are_json_numbers():
    budget_id = str(uuid.uuid4())
    budget = {
        "id": budget_id,
        "name": "Test Budget",
        "total_amount": Decimal("1500.5"),
        "donor_total_amount": Decimal("2000"),
        "estimated_exchange_rate": Decimal("0.0073125"),
    }

    with (
        patch(
            "app.api.budget_routes.get_viewable_budget_service",
            AsyncMock(return_value=budget),
        ),
        patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
    ):
        response = client.get(f"/api/v1/budgets/{budget_id}")

    assert response.status_code == 200
    assert '"total_amount":1500.5' in response.text
    assert '"estimated_exchange_rate":0.0073125' in response.text
    assert response.json()["donor_total_amount"] == 2000


def test_get_budget_endpoint_sets_budget_id_span_attribute():
    budget_id = str(uuid.uuid4())

    with (
        patch(
            "app.api.budget_routes.get_viewable_budget_service",
            AsyncMock(return_value={"id": budget_id, "name": "Test Budget"}),
        ),
        patch("app.api.budget_routes.get_viewable_budget_lines_service", return_value=[]),
        patch("app.api.budget_routes.set_span_attributes") as mock_set_span_attrs,
    ):
        client.get(f"/api/v1/budgets/{budget_id}")

    mock_set_span_attrs.assert_any_call(budget_id=uuid.UUID(budget_id))


def test_get_budget_endpoint_not_found():
    budget_id = str(uuid.uuid4())

    with patch(
        "app.api.budget_routes.get_viewable_budget_service",
        AsyncMock(side_effect=DomainError("Budget Not found", 400)),
    ):
        response = client.get(f"/api/v1/budgets/{budget_id}")

    assert response.status_code == 400
    assert response.json()["detail"] == "Budget Not found"


def test_update_budget_endpoint():
    budget_id = str(uuid.uuid4())
    payload = {"name": "Updated Budget"}

    with patch(
        "app.api.budget_routes.update_budget_service",
        AsyncMock(return_value={"id": budget_id, "name": "Updated Budget"}),
    ):
        response = client.patch(f"/api/v1/budgets/{budget_id}", json=payload)

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Budget"


def test_update_budget_endpoint_not_found_returns_404():
    budget_id = str(uuid.uuid4())

    with patch(
        "app.api.budget_routes.update_budget_service",
        AsyncMock(return_value=None),
    ):
        response = client.patch(f"/api/v1/budgets/{budget_id}", json={"name": "X"})

    assert response.status_code == 404


def test_create_budget_endpoint_sets_budget_id_span_attribute():
    budget_id = str(uuid.uuid4())
    payload = {"name": "Test Budget", "external_funder_name": "name123"}

    with (
        patch(
            "app.api.budget_routes.create_budget_service",
            AsyncMock(return_value={"id": budget_id, "name": "Test Budget"}),
        ),
        patch("app.api.budget_routes.set_span_attributes") as mock_set_span_attrs,
    ):
        client.post("/api/v1/budgets/", json=payload)

    mock_set_span_attrs.assert_any_call(budget_id=budget_id)


def test_update_budget_endpoint_sets_budget_id_span_attribute():
    budget_id = str(uuid.uuid4())

    with (
        patch(
            "app.api.budget_routes.update_budget_service",
            AsyncMock(return_value={"id": budget_id, "name": "Updated Budget"}),
        ),
        patch("app.api.budget_routes.set_span_attributes") as mock_set_span_attrs,
    ):
        client.patch(f"/api/v1/budgets/{budget_id}", json={"name": "Updated Budget"})

    mock_set_span_attrs.assert_any_call(budget_id=uuid.UUID(budget_id))


def test_delete_budget_endpoint_sets_budget_id_span_attribute():
    budget_id = str(uuid.uuid4())

    with (
        patch(
            "app.api.budget_routes.delete_budget_service",
            AsyncMock(return_value=True),
        ),
        patch("app.api.budget_routes.set_span_attributes") as mock_set_span_attrs,
    ):
        response = client.delete(f"/api/v1/budgets/{budget_id}")

    assert response.status_code == 200
    mock_set_span_attrs.assert_any_call(budget_id=uuid.UUID(budget_id))


def test_get_budgets():
    with patch(
        "app.api.budget_routes.list_budget_service",
        AsyncMock(
            return_value=[
                {"id": str(uuid.uuid4()), "name": "Budget1"},
                {"id": str(uuid.uuid4()), "name": "Budget2"},
            ]
        ),
    ):
        response = client.get("/api/v1/budgets/")

    assert response.status_code == 200
    assert len(response.json()) == 2
