import hashlib
import io
import json
import os
import uuid
import re
from decimal import Decimal, InvalidOperation

from fastapi import UploadFile, status
from sqlalchemy import select

from app.core.exceptions import DomainError
from app.models.mapping import DonorTemplateModel
from app.schemas.excel_import_schema import ExcelPrepareImportResult
from app.schemas.with_lines_schema import BudgetLineInput
from app.services.storage_client import storage_client
from app.services.template_detection.spreadsheet_reader import (
    ExcelStructureDetector,
    to_extraction_grid,
)

MAX_IMPORT_SIZE = 10 * 1024 * 1024  # under nginx's 20MB body cap, generous for a budget sheet

_AMOUNT_CLEAN_PATTERN = re.compile(r"[^\d.\-]")


def compute_structure_fingerprint(grid: list[list[str | None]]) -> str:
    """Hash of which columns are non-empty per row, ignoring values — layout
    fingerprint, stable across re-uploads of the same template."""
    skeleton = [[i for i, v in enumerate(row) if v not in (None, "")] for row in grid]
    skeleton = [row for row in skeleton if row]
    return hashlib.sha256(json.dumps(skeleton).encode()).hexdigest()


def _parse_amount(text: str | None) -> Decimal | None:
    if not text:
        return None
    cleaned = _AMOUNT_CLEAN_PATTERN.sub("", text)
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _cell(row: list[str | None], idx: int | None) -> str | None:
    if idx is None or idx < 0 or idx >= len(row):
        return None
    return row[idx]


def _extract_via_template(
    grid: list[list[str | None]], detected_structure: dict
) -> tuple[list[dict], str | None]:
    """Replay a matched template's column mapping, no AI call. Rows without
    a parseable amount update the running category instead of becoming a line."""
    category_col = detected_structure.get("category_col")
    description_col = detected_structure.get("description_col")
    amount_col = detected_structure.get("amount_col")
    currency = detected_structure.get("currency")

    lines: list[dict] = []
    current_category: str | None = None

    for row in grid:
        category_val = _cell(row, category_col)
        description_val = _cell(row, description_col)
        amount_val = _parse_amount(_cell(row, amount_col))

        if amount_val is None:
            if category_val:
                current_category = category_val
            continue

        lines.append(
            {
                "category_name": category_val or current_category or "Uncategorized",
                "description": description_val or "",
                "amount": amount_val,
                "extra_fields": None,
            }
        )

    return lines, currency


async def prepare_excel_import_service(
    db,
    valid_user: dict,
    file: UploadFile,
) -> ExcelPrepareImportResult:
    """Cleans an upload and attempts a template fingerprint match, no AI call
    and no budget creation. On no match, caller must run AI extraction on `rows`."""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise DomainError("Only .xlsx files are supported", status.HTTP_400_BAD_REQUEST)

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_IMPORT_SIZE:
        raise DomainError(
            f"File exceeds the {MAX_IMPORT_SIZE // (1024 * 1024)}MB upload limit",
            status.HTTP_400_BAD_REQUEST,
        )

    data = file.file.read()
    if not data.startswith(b"PK\x03\x04"):
        raise DomainError("File is not a valid Excel workbook", status.HTTP_400_BAD_REQUEST)

    try:
        reader = ExcelStructureDetector(io.BytesIO(data))
        cleaned_df = reader.detect_structure()
    except Exception as exc:
        raise DomainError(
            "File is not a valid Excel workbook", status.HTTP_400_BAD_REQUEST
        ) from exc

    grid = to_extraction_grid(cleaned_df)
    if not grid:
        raise DomainError("No data rows found in the uploaded file", status.HTTP_400_BAD_REQUEST)

    fingerprint = compute_structure_fingerprint(grid)

    customer_id = valid_user.get("customer_id") or valid_user["user_id"]
    storage_key = f"budget-imports/{customer_id}/{uuid.uuid4()}_{file.filename}"
    storage_client.save(storage_key, data, content_type=file.content_type)

    result = await db.execute(
        select(DonorTemplateModel)
        .where(DonorTemplateModel.fingerprint == fingerprint)
        .order_by(DonorTemplateModel.id)
        .limit(1)
    )
    matched_template = result.scalar_one_or_none()

    if matched_template and matched_template.detected_structure:
        line_dicts, currency = _extract_via_template(grid, matched_template.detected_structure)
        if not line_dicts:
            raise DomainError(
                "No budget lines could be extracted from the uploaded file",
                status.HTTP_400_BAD_REQUEST,
            )
        return ExcelPrepareImportResult(
            matched=True,
            donor_template_id=matched_template.id,
            donor_template_name=matched_template.name,
            lines=[BudgetLineInput(**line) for line in line_dicts],
            currency=currency,
        )

    return ExcelPrepareImportResult(matched=False, fingerprint=fingerprint, rows=grid)
