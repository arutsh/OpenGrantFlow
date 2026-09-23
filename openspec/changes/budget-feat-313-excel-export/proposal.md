# Proposal

## Why

A grantee owner has no way to hand a single budget's numbers to a donor, auditor, or board as a spreadsheet — every figure (budget lines, real-currency ledger, expenses) currently only exists inside the app. Donors overwhelmingly expect a multi-sheet Excel report (per the existing `KTK 2012.xls` example this proposal is grounded in), and GrandFlow already has all the underlying data (`budget_lines`, `funding_receipts`, `currency_conversions`, `report_lines`, and their FIFO allocations) — it just isn't exportable yet.

## What Changes

- Add `GET /budgets/{budget_id}/export.xlsx` (budget service): generates and streams a 3-sheet workbook for one budget, on demand (not stored), using `openpyxl` (already a dependency).
- **Sheet 1 — Original Budget**: budget lines grouped by category with subtotals, mirroring the example's layout. Each line shows its amount in the budget's `local_currency` plus a derived donor-currency estimate column (`amount ÷ estimated_exchange_rate`), consistent with how GrandFlow already treats `estimated_exchange_rate` elsewhere as an approximate, non-stored conversion (donor dashboard, budget-line toggle).
- **Sheet 2 — Budget vs. Report Dashboard**: per budget-line (and category subtotal) rows with only 3 result columns (matching the example's `I`/`J`/`K`; its interim/final-report date-range split in `E–H` is out of scope): Total Expenses (`local_currency`, direct sum of `report_lines.amount`), Total Expenses Converted (donor currency — real ledger rate for the portion covered by `ReportLineConversionAllocation`, falling back to `estimated_exchange_rate` for any unsatisfied remainder, with that estimated portion visually flagged so it's never mistaken for a real bank rate), and Deviation (budgeted-in-donor-currency minus converted actual). An income section lists every recorded `CurrencyConversion` as its own row (date, donor amount, local amount, implied rate) rather than one row per receipt, since one receipt can convert across several dates/rates.
- **Sheet 3 — List of Expenses**: one row per report-line expense; an expense whose payment was funded by more than one currency-conversion lot gets one row per allocation (subline), each carrying its own conversion date, rate, and converted amount, directly mirroring the real `ReportLineConversionAllocation` data with no aggregation.
- **Multi-template export**: a new `export_templates` table lets an organisation save named export templates. A template selects the GrandFlow renderer plus a small options blob (which sheets to include, whether to show the donor-currency estimate column, custom column header labels, whether to show the audit footer) — not a free-form layout. A seeded system-default template reproduces today's fixed 3-sheet output, so the default becomes the first row in the table rather than a branch in the code.
- **Donor→grantee sharing**: a template's `visibility` (`private` | `shared_with_grantees`) controls whether a donor's template is offered to the NGOs that donor already funds, reusing the existing `donor_grantees` relationship as the access boundary.
- Add `GET /budgets/{budget_id}/export-templates`: the templates this viewer may use for this budget (the system default, their own organisation's, and any shared by the budget's funder).
- `GET /budgets/{budget_id}/export.xlsx` accepts an optional `template_id`. Selection is always explicit: when more than one candidate exists and none is given, the request is rejected rather than silently defaulting to one.
- Frontend: an "Export to Excel" action on the single-budget view that downloads the generated file, presenting a template picker when more than one template is available; plus a template management view for creating, editing, and sharing an organisation's own templates.
- Wire the new route into all three gateway configs (`nginx-dev.conf`, `nginx.conf`, `Caddyfile`).

**Explicitly out of scope**: regenerating a budget back into a *donor's own* Excel layout (the round-trip feature already deferred by the archived `budget-export-from-excel` — actually an import feature — proposal), and the declarative JSON layout engine that would eventually let a donor describe arbitrary layouts. Templates here vary a GrandFlow-authored format through bounded options; they do not replay a donor's spreadsheet. Also out of scope: per-grantee template shares (a template is shared with all of a donor's grantees, or with none) and uploaded `.xlsx` skeletons.

## Capabilities

### New Capabilities
- `budget-excel-export`: backend generation of the 3-sheet workbook from a budget's lines, ledger, and report-line data, plus the template selection and renderer options that vary it.
- `budget-export-templates`: creating, editing, and sharing an organisation's export templates. *(Spec delta not yet authored — see tasks group 5.)*
- `budget-excel-export-ui`: the frontend entry point (template picker + download) on a single-budget view, and the template management view.

### Modified Capabilities
(none — this only reads existing `budget-currency-ledger`, `budget-reports`, and `budget-categories` data; no requirement in those specs changes)

## Impact

- **Backend**: new `services/budget/app/services/excel_export_service.py` (workbook generation), new per-budget-line rollup query (join `budget_lines`→`report_lines`, no existing precedent — closest is `dashboard_crud.budget_breakdown`, which is cross-budget, not per-line), new route in `budget_routes.py` (`GET /{budget_id}/export.xlsx`), reusing the `StreamingResponse` pattern from `attachment_routes.py`. Adds `ExportTemplateModel` + CRUD, a candidate-resolution service reusing `donor_grantee_client.check_donor_grantee_relationship`, and a `GET /{budget_id}/export-templates` route.
- **Frontend**: template picker + fetch/download handler on the budget detail view, plus a new template management view.
- **Gateway**: route addition to `nginx-dev.conf`, `nginx.conf`, `Caddyfile`.
- **Schema**: one migration adding `export_templates` (owner-scoped, unique on `(owner_customer_id, name)`) and seeding the system-default row. Workbook generation itself stays a pure read of existing tables — no generated file is ever stored.
