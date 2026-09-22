# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Export endpoint scaffolding + Sheet 1 (Original Budget) — Issue #316

- [ ] 1.0 Run `scripts/start-group.sh budget-excel-export 1` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 1.1 Add `services/budget/app/services/excel_export_service.py` with a `generate_budget_export_workbook(budget, categories, lines, ...)` entry point that creates an `openpyxl.Workbook()` and returns bytes; verify with a unit test that it returns a valid `.xlsx` (round-trips through `openpyxl.load_workbook`)
- [ ] 1.2 Implement Sheet 1 generation: budget lines grouped by category (reuse `BudgetCategoryModel` ordering), subtotal row per category, grand-total row, local-currency amount column, and a donor-currency estimate column (`amount ÷ estimated_exchange_rate`) left blank when `estimated_exchange_rate` is unset; verify with a unit test asserting cell values for a budget with 2 categories and a budget with no `estimated_exchange_rate`
- [ ] 1.3 Add `GET /budgets/{budget_id}/export.xlsx` to `services/budget/app/api/budget_routes.py`, authorized the same way as `GET /budgets/{budget_id}` (owner or funder), returning a `StreamingResponse` (mirroring `attachment_routes.py`'s pattern) with the correct `Content-Type`/`Content-Disposition`; verify with an integration test that owner and funder both get 200 and a non-owner/non-funder gets rejected
- [ ] 1.4 Wire the new route into `nginx-dev.conf`, `nginx.conf`, and `Caddyfile`; verify by confirming the route pattern matches the existing `/budgets/{budget_id}/...` entries in all three files
- [ ] 1.5 Run backend lint/tests clean for `services/budget`; PR merged (`Closes` this group's sub-issue)

## 2. Sheet 2 — Budget vs. Report Dashboard — depends on 1

- [ ] 2.1 Add `services/budget/app/crud/excel_export_crud.py` with a per-budget-line rollup query (join `budget_lines` → `report_lines`, grouped by `budget_line_id`) returning each line's total local-currency expenses and its allocations' `(amount_allocated, conversion.donor_amount, conversion.local_amount)` tuples; verify with a unit test against a seeded budget with lines spanning fully-allocated, partially-allocated, and zero-expense cases
- [ ] 2.2 Implement the converted-expense calculation in `excel_export_service.py`: real per-allocation rate for allocated amounts plus `estimated_exchange_rate` for any unsatisfied remainder, flagging a line as "includes estimate" when a remainder exists; verify with a unit test covering fully-allocated (no flag), partially-allocated (flagged, blended figure), and fully-unallocated (fully estimated, flagged) cases
- [ ] 2.3 Implement Sheet 2's income section: one row per `CurrencyConversion` for the budget (converted date, donor amount, local amount, implied rate) plus a total row; verify with a unit test using a budget with one funding receipt and multiple conversions, asserting one row per conversion
- [ ] 2.4 Implement Sheet 2's per-budget-line and category-subtotal rows (expenses local, expenses converted, deviation), reusing Sheet 1's category grouping/order and applying the estimated-portion cell style (italic + fill, per design.md Decision 4) where flagged; verify with a unit test asserting column values and that flagged cells carry the style
- [ ] 2.5 Run backend lint/tests clean for `services/budget`; PR merged (`Closes` this group's sub-issue)

## 3. Sheet 3 — List of Expenses with per-allocation sublines — depends on 1

- [ ] 3.1 Extend `excel_export_crud.py` with a query returning every report line across all of the budget's reports, each with its ordered list of allocations (or none)
- [ ] 3.2 Implement Sheet 3 generation: one row per report line when zero or one allocation exists, one row per allocation (subline) when a report line has more than one, each subline carrying its own conversion date/rate/converted amount; verify with a unit test covering an unallocated expense, a single-lot expense, and a multi-lot expense (asserting the multi-lot rows sum to the expense's full amount)
- [ ] 3.3 Run backend lint/tests clean for `services/budget`; PR merged (`Closes` this group's sub-issue)

## 4. Frontend export button — depends on 1, 2, 3

- [ ] 4.1 Add an "Export to Excel" button to the single-budget detail view in `frontend-typescript`, visible whenever the viewer has read access to the budget (owner or funder), following existing button/permission conventions on that view
- [ ] 4.2 Wire the button to `GET /budgets/{budget_id}/export.xlsx` and trigger a browser download of the response with a filename derived from the budget's name; verify manually that a downloaded file opens in Excel/LibreOffice with all 3 sheets populated
- [ ] 4.3 Add inline error handling that shows a message without navigating away when the request fails; verify with a frontend test that simulates a failed request and asserts the user stays on the budget detail view with an error shown
- [ ] 4.4 Run frontend lint/tests clean; manually verify end-to-end against a real budget with lines, receipts, multi-lot conversions, and report expenses (owner and funder logins); PR merged (`Closes` this group's sub-issue)
