import asyncio
import io
import time
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook

from app.core.exceptions import DomainError
from app.models.mapping import DonorTemplateModel
from app.services.excel_import_service import (
    compute_structure_fingerprint,
    prepare_excel_import_service,
)
from tests.factories.user import ValidUserFactory


def _build_workbook_bytes() -> bytes:
    """A realistic-shaped sheet: a category header row, two line items (one
    with a computed formula cell in a second-currency column — the bug this
    change fixes), a category-total row, and a grand-total row."""
    wb = Workbook()
    ws = wb.active
    ws.append(["1. Personnel", "", "", ""])
    ws.append(["", "Salaries", 5000, "=C3*8"])
    ws.append(["", "Travel", 200, "=C4*8"])
    ws.append(["Total Personnel", "", 5200, "=C5*8"])
    ws.append(["Total Project", "", 5200, ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload_file(data: bytes, filename: str = "Donor_budget_template.xlsx") -> MagicMock:
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    upload.file = io.BytesIO(data)
    return upload


@pytest.mark.anyio
class TestPrepareExcelImport:
    async def test_happy_path_cleans_sheet_and_excludes_totals(self, db):
        data = _build_workbook_bytes()
        upload = _upload_file(data)

        with patch("app.services.excel_import_service.storage_client.save"):
            result = await prepare_excel_import_service(db, ValidUserFactory(), upload)

        assert result.matched is False
        assert result.fingerprint
        sent_text = str(result.rows)
        assert "Total Personnel" not in sent_text
        assert "Total Project" not in sent_text
        assert "Salaries" in sent_text

    async def test_parse_runs_off_the_event_loop(self, db):
        """A slow parse must not block other coroutines (see design.md Decision 4)."""
        upload = _upload_file(_build_workbook_bytes())

        def _slow_parse(data):
            time.sleep(0.3)
            return [["Category", "Salaries", "100"]]

        with (
            patch("app.services.excel_import_service._guard_detect_and_extract_grid", _slow_parse),
            patch("app.services.excel_import_service.storage_client.save"),
        ):
            parse_task = asyncio.create_task(
                prepare_excel_import_service(db, ValidUserFactory(), upload)
            )
            start = time.monotonic()
            await asyncio.sleep(0.01)
            unrelated_tick_elapsed = time.monotonic() - start
            await parse_task

        # If the parse blocked the loop, this unrelated tick couldn't have
        # completed until the whole 0.3s "parse" was done.
        assert unrelated_tick_elapsed < 0.2

    async def test_rejects_non_xlsx_file(self, db):
        upload = _upload_file(b"not a real workbook", filename="notes.xlsx")

        with pytest.raises(DomainError) as exc_info:
            await prepare_excel_import_service(db, ValidUserFactory(), upload)

        assert exc_info.value.status_code == 400

    async def test_rejects_wrong_extension(self, db):
        upload = _upload_file(_build_workbook_bytes(), filename="budget.csv")

        with pytest.raises(DomainError) as exc_info:
            await prepare_excel_import_service(db, ValidUserFactory(), upload)

        assert exc_info.value.status_code == 400

    async def test_fingerprint_match_returns_lines_directly(self, db):
        data = _build_workbook_bytes()

        # First call (no stored template) gives us this layout's real fingerprint.
        with patch("app.services.excel_import_service.storage_client.save"):
            unmatched = await prepare_excel_import_service(
                db, ValidUserFactory(), _upload_file(data)
            )

        template = DonorTemplateModel(
            name="Acme Donor",
            fingerprint=unmatched.fingerprint,
            detected_structure={"category_col": 0, "description_col": 1, "amount_col": 2},
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

        with patch("app.services.excel_import_service.storage_client.save"):
            result = await prepare_excel_import_service(db, ValidUserFactory(), _upload_file(data))

        assert result.matched is True
        assert result.donor_template_id == template.id
        assert result.donor_template_name == "Acme Donor"
        assert {line.description for line in result.lines} == {"Salaries", "Travel"}

    async def test_no_matching_template_returns_rows_for_ai_extraction(self, db):
        data = _build_workbook_bytes()
        upload = _upload_file(data)

        with patch("app.services.excel_import_service.storage_client.save"):
            result = await prepare_excel_import_service(db, ValidUserFactory(), upload)

        assert result.matched is False
        assert result.lines is None
        assert result.rows


def test_compute_structure_fingerprint_is_stable_across_values_same_shape():
    grid_a = [["Personnel", "Salaries", "5000"], ["Personnel", "Travel", "200"]]
    grid_b = [["Personnel", "Salaries", "9999"], ["Personnel", "Travel", "1"]]
    assert compute_structure_fingerprint(grid_a) == compute_structure_fingerprint(grid_b)


def test_compute_structure_fingerprint_differs_on_layout_change():
    grid_a = [["Personnel", "Salaries", "5000"]]
    grid_b = [["Personnel", "Salaries", "5000", "Extra"]]
    assert compute_structure_fingerprint(grid_a) != compute_structure_fingerprint(grid_b)
