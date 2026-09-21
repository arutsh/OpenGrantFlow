# Proposal

## Why

A grantee owner has no way to hand a single budget's numbers to a donor, auditor, or board as a spreadsheet — every figure (budget lines, real-currency ledger, expenses) currently only exists inside the app. Donors overwhelmingly expect a multi-sheet Excel report (per the existing `KTK 2012.xls` example this proposal is grounded in), and GrandFlow already has all the underlying data (`budget_lines`, `funding_receipts`, `currency_conversions`, `report_lines`, and their FIFO allocations) — it just isn't exportable yet.

## What Changes

- Add `GET /budgets/{budget_id}/export.xlsx` (budget service): generates and streams a 3-sheet workbook for one budget, on demand (not stored), using `openpyxl` (already a dependency).
- **Sheet 1 — Original Budget**: budget lines grouped by category with subtotals, mirroring the example's layout. Each line shows its amount in the budget's `local_currency` plus a derived donor-currency estimate column (`amount ÷ estimated_exchange_rate`), consistent with how GrandFlow already treats `estimated_exchange_rate` elsewhere as an approximate, non-stored conversion (donor dashboard, budget-line toggle).
- **Sheet 2 — Budget vs. Report Dashboard**: per budget-line (and category subtotal) rows with only 3 result columns (matching the example's `I`/`J`/`K`; its interim/final-report date-range split in `E–H` is out of scope): Total Expenses (`local_currency`, direct sum of `report_lines.amount`), Total Expenses Converted (donor currency — real ledger rate for the portion covered by `ReportLineConversionAllocation`, falling back to `estimated_exchange_rate` for any unsatisfied remainder, with that estimated portion visually flagged so it's never mistaken for a real bank rate), and Deviation (budgeted-in-donor-currency minus converted actual). An income section lists every recorded `CurrencyConversion` as its own row (date, donor amount, local amount, implied rate) rather than one row per receipt, since one receipt can convert across several dates/rates.
- **Sheet 3 — List of Expenses**: one row per report-line expense; an expense whose payment was funded by more than one currency-conversion lot gets one row per allocation (subline), each carrying its own conversion date, rate, and converted amount, directly mirroring the real `ReportLineConversionAllocation` data with no aggregation.
- Frontend: an "Export to Excel" button on the single-budget view that downloads the generated file.
- Wire the new route into all three gateway configs (`nginx-dev.conf`, `nginx.conf`, `Caddyfile`).

**Explicitly out of scope**: regenerating a budget back into a *donor's own* Excel layout (the round-trip feature already deferred by the archived `budget-export-from-excel` — actually an import feature — proposal). This is a new, fixed GrandFlow-authored export format, not a donor-template replay.

## Capabilities

### New Capabilities
- `budget-excel-export`: backend generation of the 3-sheet workbook from a budget's lines, ledger, and report-line data.
- `budget-excel-export-ui`: the frontend entry point (button + download) that triggers the export on a single-budget view.

### Modified Capabilities
(none — this only reads existing `budget-currency-ledger`, `budget-reports`, and `budget-categories` data; no requirement in those specs changes)

## Impact

- **Backend**: new `services/budget/app/services/excel_export_service.py` (workbook generation), new per-budget-line rollup query (join `budget_lines`→`report_lines`, no existing precedent — closest is `dashboard_crud.budget_breakdown`, which is cross-budget, not per-line), new route in `budget_routes.py` (`GET /{budget_id}/export.xlsx`), reusing the `StreamingResponse` pattern from `attachment_routes.py`.
- **Frontend**: one button + fetch/download handler on the budget detail view; no new page.
- **Gateway**: route addition to `nginx-dev.conf`, `nginx.conf`, `Caddyfile`.
- **No schema/migration changes** — pure read of existing tables.
