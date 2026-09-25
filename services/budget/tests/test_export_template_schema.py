import pytest
from pydantic import ValidationError

from app.schemas.export_template_schema import ExportSheet, ExportTemplateOptions


class TestExportTemplateOptions:
    def test_unknown_key_rejected(self):
        with pytest.raises(ValidationError):
            ExportTemplateOptions(made_up_option=True)

    def test_missing_optional_keys_validate_to_system_default_values(self):
        options = ExportTemplateOptions()

        assert options.sheets == [
            ExportSheet.original_budget,
            ExportSheet.dashboard,
            ExportSheet.expense_list,
        ]
        assert options.show_donor_currency_estimate is True
        assert options.column_labels == {}
        assert options.show_audit_footer is True

    def test_partial_blob_fills_remaining_fields_with_defaults(self):
        options = ExportTemplateOptions(sheets=[ExportSheet.original_budget])

        assert options.sheets == [ExportSheet.original_budget]
        assert options.show_donor_currency_estimate is True
        assert options.show_audit_footer is True
