"""Orchestrates POST /chat/import-excel: prepare-import -> AI extraction
(only if no template matched) -> create_budget_with_lines.
"""

import httpx
from fastapi import UploadFile

from app.core.config import settings
from app.services.tool_registry import ToolRegistry
from shared.ai_client import AiClient, AiClientError, AiRateLimitedError, AiUnavailableError
from shared.ai_client.schemas import ExcelExtractionResult
from shared.schemas.excel_import_schema import ExcelPrepareImportResult

# Below this, a line's raw row goes into extra_fields instead of being trusted as-is.
CONFIDENCE_THRESHOLD = 0.6


class ImportExcelError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _default_budget_name(source: str) -> str:
    name = source.rsplit(".", 1)[0]
    return name.replace("_", " ").replace("-", " ").strip() or "Imported Budget"


def _should_swap_local_and_target(extraction: ExcelExtractionResult) -> bool:
    """True when local_amount/target_amount are collectively a better match
    for the sheet's own donor_total_amount if swapped — i.e. the model
    reported the donor-currency figures under local_amount and vice versa.
    Asking the model to pick which raw number is "the" local-currency
    amount proved unreliable even when it identified the currencies
    themselves correctly, so this cross-checks both reported columns
    against a figure the sheet already computed rather than trusting the
    model's per-line label. See design.md Decision 11."""
    donor_total = extraction.donor_total_amount
    if not donor_total:
        return False

    target_sum = sum(ln.target_amount for ln in extraction.lines if ln.target_amount is not None)
    if not target_sum:
        return False
    local_sum = sum(ln.local_amount for ln in extraction.lines if ln.local_amount is not None)

    err_as_is = abs(target_sum - donor_total) / donor_total
    err_swapped = abs(local_sum - donor_total) / donor_total if local_sum else float("inf")
    return err_swapped < err_as_is


def _lines_from_extraction(extraction: ExcelExtractionResult, *, swap: bool) -> list[dict]:
    lines: list[dict] = []
    for line in extraction.lines:
        local_amount, target_amount = line.local_amount, line.target_amount
        if swap:
            local_amount, target_amount = target_amount, local_amount
        amount = local_amount if local_amount is not None else target_amount

        # A cleanly resolved line never keeps model-supplied extra_fields —
        # e.g. a donor-currency value the model tucked in alongside a
        # correctly-extracted local-currency amount, redundant with the
        # platform's own estimated-rate conversion. Only a genuinely
        # low-confidence/unresolved line preserves raw data for review.
        extra_fields = None
        if line.confidence < CONFIDENCE_THRESHOLD or amount is None:
            extra_fields = dict(line.extra_fields) if line.extra_fields else {}
            extra_fields.setdefault("raw_category", line.category_name)
            extra_fields.setdefault("raw_description", line.description)
            extra_fields.setdefault("confidence", line.confidence)
            if amount is None:
                extra_fields.setdefault("amount_unresolved", True)
                amount = 0.0

        lines.append(
            {
                "category_name": line.category_name or "Uncategorized",
                "description": line.description or "",
                "amount": amount,
                "extra_fields": extra_fields,
            }
        )
    return lines


def _extract_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except Exception:
        return "The uploaded file could not be processed."
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("message") or str(detail)
    return detail or "The uploaded file could not be processed."


async def run_import_excel(
    file: UploadFile,
    *,
    token: str,
    http: httpx.AsyncClient,
    ai_client: AiClient,
    tool_registry: ToolRegistry,
) -> dict:
    prepare_resp = await http.post(
        f"{settings.BUDGET_SERVICE_URL.rstrip('/')}/budgets/excel/prepare-import",
        files={
            "file": (
                file.filename,
                await file.read(),
                file.content_type or "application/octet-stream",
            )
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )
    if prepare_resp.status_code >= 400:
        raise ImportExcelError(_extract_detail(prepare_resp), prepare_resp.status_code)

    prepared = ExcelPrepareImportResult.model_validate(prepare_resp.json())

    actual_currency = None
    donor_total_amount = None
    duration_months = None
    estimated_exchange_rate = None

    if prepared.matched:
        line_dicts = [line.model_dump(mode="json") for line in (prepared.lines or [])]
        local_currency = prepared.currency
        donor_template_id = prepared.donor_template_id
        excel_import_fingerprint = None
        excel_import_structure = None
        excel_import_lines_locked_count = None
    else:
        try:
            extraction = await ai_client.extract_budget_excel_lines(prepared.rows or [], token)
        except AiUnavailableError as exc:
            raise ImportExcelError("AI extraction is unavailable. Try again later.", 503) from exc
        except AiRateLimitedError as exc:
            raise ImportExcelError(
                "AI extraction rate limit exceeded. Try again later.", 429
            ) from exc
        except AiClientError as exc:
            raise ImportExcelError("AI extraction failed. Try again later.", 502) from exc

        swap = _should_swap_local_and_target(extraction)
        line_dicts = _lines_from_extraction(extraction, swap=swap)
        # A low-confidence (or missing) local currency is passed through as
        # unset rather than trusted — budget service falls back to the
        # owning org's own default currency. See budget-export-from-excel
        # design.md Decision 8.
        local_currency_confidence = extraction.local_currency_confidence or 0.0
        local_currency = (
            extraction.local_currency if local_currency_confidence >= CONFIDENCE_THRESHOLD else None
        )
        actual_currency = extraction.target_currency
        donor_total_amount = extraction.donor_total_amount
        duration_months = extraction.duration_months
        if donor_total_amount:
            line_total = sum(line["amount"] for line in line_dicts)
            estimated_exchange_rate = line_total / donor_total_amount
        donor_template_id = None
        # Swap-corrected so a fingerprint-matched replay reads the verified local-currency column.
        amount_col = extraction.column_map.amount_col
        if swap:
            amount_col = extraction.column_map.target_amount_col
        if amount_col is None:
            # No reliable column to replay from — skip persisting a fingerprint/structure.
            excel_import_fingerprint = None
            excel_import_structure = None
        else:
            excel_import_fingerprint = prepared.fingerprint
            excel_import_structure = {
                "category_col": extraction.column_map.category_col,
                "description_col": extraction.column_map.description_col,
                "amount_col": amount_col,
                "currency": local_currency,
            }
        excel_import_lines_locked_count = len(line_dicts)

    if not line_dicts:
        raise ImportExcelError("No budget lines could be extracted from the uploaded file", 400)

    budget_name_source = prepared.donor_template_name or file.filename or "Imported Budget"
    params = {
        "budget_name": _default_budget_name(budget_name_source),
        "external_funder_name": prepared.donor_template_name or "Imported budget",
        "local_currency": local_currency,
        "actual_currency": actual_currency,
        "donor_total_amount": donor_total_amount,
        "estimated_exchange_rate": estimated_exchange_rate,
        "duration_months": duration_months,
        "lines": line_dicts,
        "donor_template_id": donor_template_id,
        "excel_import_fingerprint": excel_import_fingerprint,
        "excel_import_structure": excel_import_structure,
        "excel_import_lines_locked_count": excel_import_lines_locked_count,
    }

    result = await tool_registry.call_tool("create_budget_with_lines", params, token=token)
    if not result.success:
        raise ImportExcelError(result.message, 502)

    return {"id": result.created_resource_id}
