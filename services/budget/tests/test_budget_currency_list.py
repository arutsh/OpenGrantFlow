"""GET /budgets/currencies serves the same list budget writes validate against."""

from fastapi.testclient import TestClient

from main import app
from shared.services.currency_service import validate_currency


def test_returns_sorted_code_name_entries(make_client):
    response = make_client().get("/api/v1/budgets/currencies")

    assert response.status_code == 200
    entries = response.json()
    codes = [e["code"] for e in entries]
    assert codes == sorted(codes)
    assert {"AMD", "JPY"} <= set(codes)
    assert all(set(e) == {"code", "name"} and e["name"] for e in entries)


def test_every_returned_code_passes_validation(make_client):
    entries = make_client().get("/api/v1/budgets/currencies").json()
    assert all(validate_currency(e["code"]) for e in entries)


def test_requires_authentication():
    app.dependency_overrides = {}
    assert TestClient(app).get("/api/v1/budgets/currencies").status_code == 401
