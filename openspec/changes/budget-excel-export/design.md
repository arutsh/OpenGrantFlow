# Design

## Context

See proposal.md - Why. Relevant existing data model (all in `services/budget/app/models/`):
- `BudgetModel`/`BudgetLineModel`/`BudgetCategoryModel` (`budget.py`): budget lines store `amount` in the budget's `local_currency`; `actual_currency` is the donor's currency; `estimated_exchange_rate` (local ÷ donor, e.g. AMD per EUR) is a planning-time estimate, never a stored per-line figure — existing code (donor dashboard, budget-line currency toggle) already treats it as a derived, render-time-only conversion, never persisted as a second amount.
- `FundingReceiptModel`/`CurrencyConversionModel`/`ReportLineConversionAllocationModel` (`currency_ledger.py`): a receipt (donor currency landed) and a conversion (one real bank FX event, rate = `local_amount ÷ donor_amount`) are **not linked 1:1** — only aggregate-balanced. A report-line expense (`ReportLineModel.amount`, in `local_currency`) is allocated FIFO across unconsumed conversion lots (`currency_ledger_services.allocate_fifo_service`), producing zero or more allocation rows per expense.
- No existing per-budget-line planned-vs-actual rollup query exists; `dashboard_crud.budget_breakdown` is the closest precedent but aggregates cross-budget, not per-line.
- `openpyxl==3.1.5` is already a dependency (currently import-only, via `excel_import_service.py`); no new package needed for writing.
- `attachment_routes.py` already establishes the `StreamingResponse` file-download pattern for this service.

## Goals / Non-Goals

**Goals:**
- Generate one workbook per request, entirely from live data, with no new tables or stored artifacts.
- Reuse the currency-ledger's real allocation data wherever it exists; only fall back to the planning-time estimate for the genuinely unresolved gap, and mark that gap visibly.

**Non-Goals:**
- Donor-template-shaped round-trip export (deferred; see proposal).
- Caching, background generation, or emailing the file — synchronous request/response only, matching the size of a single budget's data.
- Any change to how receipts, conversions, or allocations are recorded (`ledger-budget`'s in-flight edit/delete/reset work is unrelated and unaffected).

## Decisions

**1. New per-budget-line rollup query, not a reuse of `dashboard_crud.budget_breakdown`.**
That function sums conversions/expenses per *budget*, across all budgets a customer owns — the export needs the same shape of number (converted, spent) but grouped by *budget_line_id* within one budget, plus the allocation-level rate detail `budget_breakdown` never needed. New function(s) live in a new `services/budget/app/crud/excel_export_crud.py`, following the same subquery pattern (`group_by` + `outerjoin`) rather than N+1 per-line queries.

**2. Converted-expense figure blends real allocation rates with `estimated_exchange_rate` for the unsatisfied remainder, computed per report line then summed per budget line.**
For each report line: sum `allocation.amount_allocated × (conversion.donor_amount ÷ conversion.local_amount)` across its allocations (real rate, since `amount_allocated` is in `local_currency`), then add `(report_line.amount − Σallocation.amount_allocated) ÷ estimated_exchange_rate` for any remainder. This mirrors the existing precedent of using `estimated_exchange_rate` as an approximate stand-in (donor dashboard, budget-line toggle) rather than inventing a new conversion rule. A budget line is flagged "includes estimate" in the export if any of its report lines have a non-zero unsatisfied remainder.
*Alternative considered*: omit the unsatisfied remainder entirely (leave it unconverted/blank). Rejected per explicit product decision — donors expect the dashboard total to foot to something close to the full spend, and GrandFlow already accepts approximate figures elsewhere rather than showing gaps.

**3. Workbook generated synchronously in the request/response cycle via `openpyxl.Workbook()`, streamed with `StreamingResponse` (mirroring `attachment_routes.py`), not written to storage first.**
A single budget's data (lines, ledger, report lines) is small; no need for the async/background pattern used elsewhere (e.g. Celery) for larger jobs.

**4. Sheet 2's estimated-portion flag is a cell style (e.g. italic + light fill + a legend row), not a separate column.**
Keeps the sheet's column count matching the user's I/J/K scope instead of doubling columns for a rare partial-estimate case.

## Risks / Trade-offs

- [A budget with many report lines/allocations could make generation slow] → Out of scope for a "simple export" of one budget; single-budget expense volume in practice is small (tens to low hundreds of lines), revisit only if real usage shows otherwise.
- [`estimated_exchange_rate` unset on an older or draft budget leaves Sheet 1's donor-currency column and Sheet 2's deviation column blank for that budget] → Matches existing GrandFlow convention (donor dashboard already excludes rather than fabricates); the export's local-currency figures are still fully populated.
- [Category subtotal rows in Sheet 2 need the same rollup as Sheet 1's category grouping] → Reuse the same category-grouping logic/order between Sheet 1 and Sheet 2 rather than deriving it twice, to avoid the two sheets silently disagreeing on category order or membership.
