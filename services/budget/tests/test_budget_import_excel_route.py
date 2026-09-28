import io
import zipfile
from unittest.mock import AsyncMock, patch

from app.schemas.excel_import_schema import ExcelPrepareImportResult

_MINIMAL_XLSX_EXTRAS = {
    "[Content_Types].xml": "<Types/>",
    "_rels/.rels": "<Relationships/>",
    "xl/workbook.xml": "<workbook/>",
}


def _sparse_huge_range_workbook_bytes() -> bytes:
    """A ~200-byte file whose used range, if openpyxl ever materialized it,
    would be ~17 billion cells — the attack `workbook_limits` guards against."""
    sheet_xml = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row><c r="A1"/><c r="XFD1048576"/></row></sheetData></worksheet>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in _MINIMAL_XLSX_EXTRAS.items():
            zf.writestr(name, content)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


class TestPrepareExcelImportRoute:
    def test_uploads_file_and_returns_prepared_result(self, make_client):
        client = make_client()
        prepared = ExcelPrepareImportResult(matched=False, fingerprint="fp-1", rows=[["a"]])

        with patch(
            "app.api.budget_routes.prepare_excel_import_service",
            AsyncMock(return_value=prepared),
        ) as mock_prepare:
            resp = client.post(
                "/api/v1/budgets/excel/prepare-import",
                files={
                    "file": (
                        "budget.xlsx",
                        b"fake-bytes",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        assert resp.status_code == 200
        assert resp.json() == prepared.model_dump()
        mock_prepare.assert_called_once()
        # db, valid_user, file — the uploaded file is the last positional arg
        uploaded_file = mock_prepare.call_args.args[-1]
        assert uploaded_file.filename == "budget.xlsx"

    def test_requires_authentication(self, make_client):
        client = make_client()
        client.app.dependency_overrides = {}
        resp = client.post(
            "/api/v1/budgets/excel/prepare-import",
            files={"file": ("budget.xlsx", b"fake-bytes", "application/octet-stream")},
        )
        assert resp.status_code == 401

    def test_oversized_workbook_is_rejected_before_storage(self, make_client):
        """Exercises the real service (not mocked) so the workbook_limits guard
        actually runs, ahead of ExcelStructureDetector and the storage write."""
        client = make_client()

        with patch("app.services.excel_import_service.storage_client.save") as mock_save:
            resp = client.post(
                "/api/v1/budgets/excel/prepare-import",
                files={
                    "file": (
                        "budget.xlsx",
                        _sparse_huge_range_workbook_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Sheet has more than 10,000 rows"
        mock_save.assert_not_called()

    def test_malformed_workbook_is_rejected_as_invalid_not_oversized(self, make_client):
        client = make_client()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in _MINIMAL_XLSX_EXTRAS.items():
                zf.writestr(name, content)
            zf.writestr(
                "xl/worksheets/sheet1.xml", '<worksheet><row><c r="bogus"/></row></worksheet>'
            )

        with patch("app.services.excel_import_service.storage_client.save") as mock_save:
            resp = client.post(
                "/api/v1/budgets/excel/prepare-import",
                files={
                    "file": (
                        "budget.xlsx",
                        buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "File is not a valid Excel workbook"
        mock_save.assert_not_called()
