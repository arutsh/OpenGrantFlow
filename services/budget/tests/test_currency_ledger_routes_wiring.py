"""Route-level span-attribute wiring for the funding-receipt and currency-conversion routers.
Service-layer ledger tests live in test_currency_ledger.py."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4


class TestFundingReceiptRoutesWiring:
    def test_create_route_sets_span_attributes(self, make_client):
        client = make_client()
        budget_id = uuid4()
        receipt_id = uuid4()
        with (
            patch(
                "app.api.funding_receipt_routes.record_receipt_service",
                return_value=SimpleNamespace(id=receipt_id),
            ),
            patch("app.api.funding_receipt_routes.set_span_attributes") as mock_set_span_attrs,
        ):
            client.post(
                "/api/v1/funding-receipts/",
                json={
                    "budget_id": str(budget_id),
                    "amount": 1000.0,
                    "received_at": "2026-01-01",
                },
            )
        mock_set_span_attrs.assert_any_call(budget_id=budget_id)
        mock_set_span_attrs.assert_any_call(funding_receipt_id=receipt_id)

    def test_update_route_sets_span_attributes(self, make_client):
        client = make_client()
        receipt_id = uuid4()
        with (
            patch(
                "app.api.funding_receipt_routes.update_receipt_service",
                return_value=SimpleNamespace(id=receipt_id),
            ) as mock_update,
            patch("app.api.funding_receipt_routes.set_span_attributes") as mock_set_span_attrs,
        ):
            client.patch(f"/api/v1/funding-receipts/{receipt_id}", json={"amount": 5.0})
        mock_set_span_attrs.assert_any_call(funding_receipt_id=receipt_id)
        mock_update.assert_awaited_once()

    def test_update_route_rejects_explicit_null(self, make_client):
        client = make_client()
        with patch("app.api.funding_receipt_routes.update_receipt_service") as mock_update:
            response = client.patch(f"/api/v1/funding-receipts/{uuid4()}", json={"amount": None})
        assert response.status_code == 422
        mock_update.assert_not_called()

    def test_delete_route_sets_span_attributes(self, make_client):
        client = make_client()
        receipt_id = uuid4()
        with (
            patch(
                "app.api.funding_receipt_routes.delete_receipt_service",
                return_value=True,
            ),
            patch("app.api.funding_receipt_routes.set_span_attributes") as mock_set_span_attrs,
        ):
            response = client.delete(f"/api/v1/funding-receipts/{receipt_id}")
        mock_set_span_attrs.assert_any_call(funding_receipt_id=receipt_id)
        assert response.json() == {"success": True}


class TestCurrencyConversionRoutesWiring:
    def test_create_route_sets_span_attributes(self, make_client):
        client = make_client()
        budget_id = uuid4()
        conversion_id = uuid4()
        with (
            patch(
                "app.api.currency_conversion_routes.record_conversion_service",
                return_value=SimpleNamespace(id=conversion_id),
            ),
            patch("app.api.currency_conversion_routes.set_span_attributes") as mock_set_span_attrs,
        ):
            client.post(
                "/api/v1/currency-conversions/",
                json={
                    "budget_id": str(budget_id),
                    "donor_amount": 1000.0,
                    "local_amount": 800.0,
                    "converted_at": "2026-01-01",
                },
            )
        mock_set_span_attrs.assert_any_call(budget_id=budget_id)
        mock_set_span_attrs.assert_any_call(conversion_id=conversion_id)

    def test_update_route_sets_span_attributes(self, make_client):
        client = make_client()
        conversion_id = uuid4()
        with (
            patch(
                "app.api.currency_conversion_routes.update_conversion_service",
                return_value=SimpleNamespace(id=conversion_id),
            ) as mock_update,
            patch("app.api.currency_conversion_routes.set_span_attributes") as mock_set_span_attrs,
        ):
            client.patch(
                f"/api/v1/currency-conversions/{conversion_id}", json={"local_amount": 5.0}
            )
        mock_set_span_attrs.assert_any_call(conversion_id=conversion_id)
        mock_update.assert_awaited_once()

    def test_update_route_rejects_explicit_null(self, make_client):
        client = make_client()
        with patch("app.api.currency_conversion_routes.update_conversion_service") as mock_update:
            response = client.patch(
                f"/api/v1/currency-conversions/{uuid4()}", json={"donor_amount": None}
            )
        assert response.status_code == 422
        mock_update.assert_not_called()

    def test_delete_route_sets_span_attributes(self, make_client):
        client = make_client()
        conversion_id = uuid4()
        with (
            patch(
                "app.api.currency_conversion_routes.delete_conversion_service",
                return_value=True,
            ),
            patch("app.api.currency_conversion_routes.set_span_attributes") as mock_set_span_attrs,
        ):
            response = client.delete(f"/api/v1/currency-conversions/{conversion_id}")
        mock_set_span_attrs.assert_any_call(conversion_id=conversion_id)
        assert response.json() == {"success": True}

    def test_reset_route_sets_span_attributes(self, make_client):
        client = make_client()
        budget_id = uuid4()
        result = {"receipts_deleted": 2, "conversions_deleted": 1}
        with (
            patch(
                "app.api.currency_conversion_routes.reset_ledger_service",
                return_value=result,
            ),
            patch("app.api.currency_conversion_routes.set_span_attributes") as mock_set_span_attrs,
        ):
            response = client.post(f"/api/v1/currency-conversions/reset/{budget_id}")
        mock_set_span_attrs.assert_any_call(budget_id=budget_id)
        assert response.json() == result
