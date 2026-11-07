"""Tests for run_import_excel — POST /chat/import-excel's orchestration
(budget-export-from-excel design.md Decision 7): budget's prepare-import
step, then ai's extraction endpoint only on no template match, then the
create_budget_with_lines tool.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.import_excel import ImportExcelError, run_import_excel
from app.services.tool_registry import ToolResult
from shared.ai_client import AiClientError, AiRateLimitedError, AiUnavailableError
from shared.ai_client.schemas import (
    ExcelExtractionColumnMap,
    ExcelExtractionLine,
    ExcelExtractionResult,
)

pytestmark = pytest.mark.anyio


def _upload_file(filename: str = "Donor_budget.xlsx") -> MagicMock:
    file = MagicMock()
    file.filename = filename
    file.content_type = "application/octet-stream"
    file.read = AsyncMock(return_value=b"PK\x03\x04fake")
    return file


def _http_response(status_code: int, json_body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status_code, json=json_body, request=httpx.Request("POST", "http://budget/x")
    )


def _http(response: httpx.Response) -> MagicMock:
    http = MagicMock()
    http.post = AsyncMock(return_value=response)
    return http


def _tool_registry(result: ToolResult) -> MagicMock:
    registry = MagicMock()
    registry.call_tool = AsyncMock(return_value=result)
    return registry


class TestFingerprintMatch:
    async def test_matched_template_skips_ai_and_creates_budget(self):
        http = _http(
            _http_response(
                200,
                {
                    "matched": True,
                    "donor_template_id": 7,
                    "donor_template_name": "USAID Template",
                    "lines": [{"category_name": "Travel", "description": "Flights", "amount": 500}],
                    "currency": "USD",
                },
            )
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock()
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-1"))

        result = await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        assert result == {"id": "b-1"}
        ai_client.extract_budget_excel_lines.assert_not_awaited()
        registry.call_tool.assert_awaited_once()
        name, params = registry.call_tool.call_args.args
        assert name == "create_budget_with_lines"
        assert params["donor_template_id"] == 7
        assert params["external_funder_name"] == "USAID Template"
        assert params["local_currency"] == "USD"
        assert params["lines"] == [
            {
                "category_name": "Travel",
                "description": "Flights",
                "amount": 500.0,
                "extra_fields": None,
            }
        ]
        assert params["excel_import_fingerprint"] is None


class TestNoMatchCallsAi:
    async def test_extracts_via_ai_and_creates_budget(self):
        http = _http(
            _http_response(
                200,
                {"matched": False, "fingerprint": "fp-1", "rows": [["Travel", "Flights", "500"]]},
            )
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency="EUR",
                local_currency_confidence=0.9,
                lines=[
                    ExcelExtractionLine(
                        category_name="Travel",
                        description="Flights",
                        local_amount=500,
                        confidence=0.9,
                    )
                ],
                column_map=ExcelExtractionColumnMap(
                    category_col=0, description_col=1, amount_col=2
                ),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-2"))

        result = await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        assert result == {"id": "b-2"}
        ai_client.extract_budget_excel_lines.assert_awaited_once_with(
            [["Travel", "Flights", "500"]], "tok"
        )
        name, params = registry.call_tool.call_args.args
        assert name == "create_budget_with_lines"
        assert params["donor_template_id"] is None
        assert params["excel_import_fingerprint"] == "fp-1"
        assert params["excel_import_lines_locked_count"] == 1
        assert params["lines"] == [
            {
                "category_name": "Travel",
                "description": "Flights",
                "amount": 500,
                "extra_fields": None,
            }
        ]

    async def test_low_confidence_line_routed_into_extra_fields(self):
        http = _http(
            _http_response(200, {"matched": False, "fingerprint": "fp-2", "rows": [["a", "b"]]})
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency=None,
                lines=[
                    ExcelExtractionLine(
                        category_name="?", description="?", local_amount=None, confidence=0.2
                    )
                ],
                column_map=ExcelExtractionColumnMap(),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-3"))

        await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        line = registry.call_tool.call_args.args[1]["lines"][0]
        assert line["amount"] == 0.0
        assert line["extra_fields"]["amount_unresolved"] is True

    async def test_high_confidence_line_drops_model_supplied_extra_fields(self):
        """A cleanly resolved line never carries model-supplied extra_fields
        through — e.g. a donor-currency value the model tucked in alongside
        a correctly-extracted local-currency amount is redundant with the
        platform's own estimated-rate conversion, not something to persist."""
        http = _http(
            _http_response(200, {"matched": False, "fingerprint": "fp-6", "rows": [["a", "b"]]})
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency="AMD",
                local_currency_confidence=0.95,
                lines=[
                    ExcelExtractionLine(
                        category_name="Activities",
                        description="Coffee Break",
                        local_amount=225000.0,
                        confidence=0.9,
                        extra_fields={"costs_in_euro": 500},
                    )
                ],
                column_map=ExcelExtractionColumnMap(),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-6"))

        await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        line = registry.call_tool.call_args.args[1]["lines"][0]
        assert line["amount"] == 225000.0
        assert line["extra_fields"] is None

    async def test_invalid_extracted_currencies_are_dropped_to_unset(self):
        http = _http(
            _http_response(
                200,
                {"matched": False, "fingerprint": "fp-c", "rows": [["A", "B", "1"]]},
            )
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency="US Dollars",
                local_currency_confidence=0.95,
                target_currency="$",
                lines=[
                    ExcelExtractionLine(
                        category_name="A",
                        description="B",
                        local_amount=1.0,
                        target_amount=None,
                        confidence=0.9,
                    )
                ],
                column_map=ExcelExtractionColumnMap(
                    category_col=0, description_col=1, amount_col=2
                ),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-c"))

        await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        params = registry.call_tool.call_args.args[1]
        assert params["local_currency"] is None
        assert params["actual_currency"] is None
        assert params["excel_import_structure"]["currency"] is None

    async def test_dual_currency_sheet_uses_local_amount_and_derives_exchange_rate(self):
        """See budget-export-from-excel design.md Decision 8: line amounts come
        from the local-currency column, donor_total_amount is the sheet's own
        total in the target currency, and estimated_exchange_rate is computed
        from the two rather than asked of the model."""
        http = _http(
            _http_response(
                200,
                {
                    "matched": False,
                    "fingerprint": "fp-4",
                    "rows": [["Activities", "Coffee", "225000"]],
                },
            )
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency="AMD",
                local_currency_confidence=0.95,
                target_currency="EUR",
                donor_total_amount=100.0,
                duration_months=12,
                lines=[
                    ExcelExtractionLine(
                        category_name="Activities",
                        description="Coffee Break",
                        local_amount=450.0,
                        target_amount=100.0,
                        confidence=0.9,
                    )
                ],
                column_map=ExcelExtractionColumnMap(
                    category_col=0, description_col=1, amount_col=2, target_amount_col=3
                ),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-4"))

        await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        params = registry.call_tool.call_args.args[1]
        assert params["local_currency"] == "AMD"
        assert params["actual_currency"] == "EUR"
        assert params["donor_total_amount"] == 100.0
        assert params["duration_months"] == 12
        assert params["estimated_exchange_rate"] == 4.5  # 450 local / 100 target

    async def test_swaps_local_and_target_when_model_mislabels_them(self):
        """Regression test: even with local_currency/target_currency
        identified correctly, the model has been observed putting the
        donor-currency figures under local_amount and vice versa. Detected
        and corrected by checking which assignment's summed target_amount
        actually matches the sheet's own donor_total_amount — see
        design.md Decision 11."""
        http = _http(
            _http_response(
                200,
                {
                    "matched": False,
                    "fingerprint": "fp-7",
                    "rows": [
                        ["Activities", "Coffee", "225000", "500"],
                        ["Activities", "Rent", "180000", "400"],
                    ],
                },
            )
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency="AMD",
                local_currency_confidence=0.95,
                target_currency="EUR",
                donor_total_amount=900.0,
                lines=[
                    # Mislabeled: local_amount/target_amount are swapped
                    # relative to the sheet (225000/500 and 180000/400).
                    ExcelExtractionLine(
                        category_name="Activities",
                        description="Coffee",
                        local_amount=500.0,
                        target_amount=225000.0,
                        confidence=0.9,
                    ),
                    ExcelExtractionLine(
                        category_name="Activities",
                        description="Rent",
                        local_amount=400.0,
                        target_amount=180000.0,
                        confidence=0.9,
                    ),
                ],
                column_map=ExcelExtractionColumnMap(
                    category_col=0, description_col=1, amount_col=3, target_amount_col=2
                ),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-7"))

        await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        params = registry.call_tool.call_args.args[1]
        amounts = [line["amount"] for line in params["lines"]]
        assert amounts == [225000.0, 180000.0]
        assert params["excel_import_structure"]["amount_col"] == 2

    async def test_swap_without_target_amount_col_skips_fingerprint(self):
        """Regression test: swap-correction can trigger from per-line values alone,
        independently of column_map. If target_amount_col is missing there's no
        reliable column to replay from, so no fingerprint/structure is saved
        rather than persisting amount_col=None, which would break every future
        replay of that layout (extracting zero lines forever)."""
        http = _http(
            _http_response(
                200,
                {
                    "matched": False,
                    "fingerprint": "fp-8",
                    "rows": [["Activities", "Coffee", "225000", "500"]],
                },
            )
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency="AMD",
                local_currency_confidence=0.95,
                target_currency="EUR",
                donor_total_amount=225000.0,
                lines=[
                    # Mislabeled (local_sum matches donor_total, not target_sum) so
                    # _should_swap_local_and_target returns True.
                    ExcelExtractionLine(
                        category_name="Activities",
                        description="Coffee",
                        local_amount=225000.0,
                        target_amount=500.0,
                        confidence=0.9,
                    )
                ],
                column_map=ExcelExtractionColumnMap(
                    category_col=0, description_col=1, amount_col=3, target_amount_col=None
                ),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-8"))

        await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        params = registry.call_tool.call_args.args[1]
        assert params["excel_import_fingerprint"] is None
        assert params["excel_import_structure"] is None

    async def test_low_confidence_local_currency_falls_back_to_unset(self):
        """Below the confidence threshold, local_currency is passed through as
        unset rather than trusted — budget service applies the org's own
        default currency instead."""
        http = _http(
            _http_response(200, {"matched": False, "fingerprint": "fp-5", "rows": [["a", "b"]]})
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(
            return_value=ExcelExtractionResult(
                local_currency="XYZ",
                local_currency_confidence=0.3,
                lines=[
                    ExcelExtractionLine(
                        category_name="A", description="B", local_amount=10.0, confidence=0.9
                    )
                ],
                column_map=ExcelExtractionColumnMap(),
            )
        )
        registry = _tool_registry(ToolResult(success=True, message="ok", created_resource_id="b-5"))

        await run_import_excel(
            _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
        )

        params = registry.call_tool.call_args.args[1]
        assert params["local_currency"] is None

    @pytest.mark.parametrize(
        "exc,expected_status",
        [
            (AiUnavailableError(), 503),
            (AiRateLimitedError(retry_after=0), 429),
            (AiClientError("boom"), 502),
        ],
    )
    async def test_ai_client_failures_map_to_status_codes(self, exc, expected_status):
        http = _http(
            _http_response(200, {"matched": False, "fingerprint": "fp-3", "rows": [["a"]]})
        )
        ai_client = MagicMock()
        ai_client.extract_budget_excel_lines = AsyncMock(side_effect=exc)
        registry = _tool_registry(ToolResult(success=True, message="ok"))

        with pytest.raises(ImportExcelError) as exc_info:
            await run_import_excel(
                _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
            )

        assert exc_info.value.status_code == expected_status


class TestPrepareImportFailure:
    async def test_invalid_file_relayed_as_import_error(self):
        http = _http(_http_response(400, {"detail": "File is not a valid Excel workbook"}))
        ai_client = MagicMock()
        registry = _tool_registry(ToolResult(success=True, message="ok"))

        with pytest.raises(ImportExcelError) as exc_info:
            await run_import_excel(
                _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
            )

        assert exc_info.value.status_code == 400
        assert "not a valid Excel workbook" in exc_info.value.message


class TestNoLinesExtracted:
    async def test_matched_but_empty_lines_raises_400(self):
        http = _http(_http_response(200, {"matched": True, "lines": [], "donor_template_id": 1}))
        ai_client = MagicMock()
        registry = _tool_registry(ToolResult(success=True, message="ok"))

        with pytest.raises(ImportExcelError) as exc_info:
            await run_import_excel(
                _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
            )

        assert exc_info.value.status_code == 400


class TestCreateBudgetToolFailure:
    async def test_tool_failure_raises_502(self):
        http = _http(
            _http_response(
                200,
                {
                    "matched": True,
                    "donor_template_id": 1,
                    "lines": [{"category_name": "A", "description": "B", "amount": 1}],
                },
            )
        )
        ai_client = MagicMock()
        registry = _tool_registry(ToolResult(success=False, message="Failed to create budget"))

        with pytest.raises(ImportExcelError) as exc_info:
            await run_import_excel(
                _upload_file(), token="tok", http=http, ai_client=ai_client, tool_registry=registry
            )

        assert exc_info.value.status_code == 502
