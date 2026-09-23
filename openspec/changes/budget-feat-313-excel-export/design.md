# Design

## Context

See proposal.md - Why. Relevant existing data model (all in `services/budget/app/models/`):
- `BudgetModel`/`BudgetLineModel`/`BudgetCategoryModel` (`budget.py`): budget lines store `amount` in the budget's `local_currency`; `actual_currency` is the donor's currency; `estimated_exchange_rate` (local ÷ donor, e.g. AMD per EUR) is a planning-time estimate, never a stored per-line figure — existing code (donor dashboard, budget-line currency toggle) already treats it as a derived, render-time-only conversion, never persisted as a second amount.
- `FundingReceiptModel`/`CurrencyConversionModel`/`ReportLineConversionAllocationModel` (`currency_ledger.py`): a receipt (donor currency landed) and a conversion (one real bank FX event, rate = `local_amount ÷ donor_amount`) are **not linked 1:1** — only aggregate-balanced. A report-line expense (`ReportLineModel.amount`, in `local_currency`) is allocated FIFO across unconsumed conversion lots (`currency_ledger_services.allocate_fifo_service`), producing zero or more allocation rows per expense.
- No existing per-budget-line planned-vs-actual rollup query exists; `dashboard_crud.budget_breakdown` is the closest precedent but aggregates cross-budget, not per-line.
- `openpyxl==3.1.5` is already a dependency (currently import-only, via `excel_import_service.py`); no new package needed for writing.
- `attachment_routes.py` already establishes the `StreamingResponse` file-download pattern for this service.
- `DonorGranteeModel` (`services/users/app/models/customer.py`) records which NGOs a donor funds; the budget service already reaches it through `donor_grantee_client.check_donor_grantee_relationship`, deliberately uncached so a revoked relationship takes effect on the very next call.
- The existing `donor_templates` table (`budget_donor_template_crud.py`, migration `000012_add_donor_template_fingerprint.py`) is a different thing wearing a similar name: an *import*-side layout fingerprint cache, not an export template. Its known problems (no tenant scoping, no uniqueness, no review gate) are tracked separately in the `budget-template-storing` proposal and are not addressed here.

## Goals / Non-Goals

**Goals:**
- Generate one workbook per request, entirely from live data. The only stored artifact is the template that selects the export's options — never the generated workbook itself.
- Make today's fixed format the seeded system-default template, so multi-template support adds a row rather than a branch.
- Reuse the currency-ledger's real allocation data wherever it exists; only fall back to the planning-time estimate for the genuinely unresolved gap, and mark that gap visibly.

**Non-Goals:**
- Donor-template-shaped round-trip export (deferred; see proposal).
- A declarative layout engine. Templates vary bounded renderer options, not arbitrary cell layout (see Decision 9).
- Per-grantee template shares. Visibility is all-of-a-donor's-grantees or private (see Decision 7).
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

**5. Sheet 1 is a live formula chain, not values computed by openpyxl: every number above the raw per-line amount is an Excel formula, not a Python-computed literal.**
Per-line local amount is the only literal value. Each category's Detailed Budget subtotal is `=SUM(<its line cells>)`; each line's donor-currency estimate is `=<local cell>/<rate cell>`; each subtotal's estimate is `=SUM(<its line estimate cells>)`. Budget Summary doesn't recompute anything — each category row there is a direct cell reference to that category's own Detailed Budget subtotal (`=C19`/`=D19`), and its TOTAL row is `=SUM(...)` over those reference rows. The footer's "Total expenditures" row adds the Detailed Budget subtotal cells directly (`=C19+C25`), independent of Budget Summary's TOTAL, mirroring the hand-built reference file (`uploads/budget/Demo budget 3 (1).xlsx`) the user supplied as the exact target — one deviation: that file's Budget Summary rows both referenced the *same* subtotal cell (a copy-paste slip), corrected here so each category row references its own. Distinct from the deferred donor-template-replay change (`budget-export-from-excel`'s follow-on), where static values were floated specifically to dodge `openpyxl.insert_rows()` not adjusting existing formula ranges on row insertion — Sheet 1 is generated fresh on every request (no row insertion into a pre-existing file), so that risk doesn't apply, and a live chain lets a donor hand-edit any line amount or the rate cell and see every subtotal/total/estimate recalculate. Trade-off: tests assert formula strings for every non-leaf cell, since openpyxl never evaluates formulas itself (verified end-to-end by round-tripping a sample workbook through `soffice --headless --convert-to csv`, confirming LibreOffice's formula engine actually computes the expected totals, not just that the formula strings parse).

**6. Header's organisation/donor name comes from `customer_client.get_customer_cached`, not a new field on `BudgetModel`.**
`owner_id`/`funding_customer_id` already resolve to a customer name via the existing service-to-service lookup (same pattern as `budget_services.py`'s `local_currency` fallback); no new cross-service plumbing needed. `external_funder_name` is the fallback when `funding_customer_id` is unset. "Project Ref.no." was considered and deliberately dropped — no backing field exists on `BudgetModel` and none was added for this change.

**7. Templates are owner-scoped rows with a coarse `visibility` enum; per-grantee shares are deferred behind an unchanged resolver signature.**
`export_templates` carries `owner_customer_id`, `name`, `visibility` (`private` | `shared_with_grantees`), and the options blob, unique on `(owner_customer_id, name)`. A grantee may use a donor's template only when that template is `shared_with_grantees` **and** `check_donor_grantee_relationship(donor, grantee)` returns true — the relationship is the access boundary, so revoking it revokes template access immediately, with no cache to expire. Every CRUD function takes the actor's `customer_id` in its signature, so an unscoped query is not expressible; this is a direct response to the unscoped-lookup defect found in `donor_templates` (see `budget-template-storing` problem 1).
*Alternative considered*: an `export_template_shares` join table for per-grantee grants up front. Deferred — the stated need is "a donor publishes this to its grantees", which the enum covers. The resolver is specified as `list_candidate_templates(actor, budget) -> list[Template]` precisely so adding the join table later changes that function's body and nothing above it.

**8. Template selection is always explicit; there is no silent fallback cascade.**
`GET /budgets/{budget_id}/export-templates` returns the candidates (each tagged `system` | `own` | `donor`). On export: `template_id` omitted with exactly one candidate uses it; omitted with more than one is rejected (400); an id outside the candidate list is rejected (403). No precedence rule between "my org's template" and "my funder's template" is defined, because nothing ever picks between them automatically.
*Alternative considered*: a resolution cascade (explicit → budget default → donor default → org default → system). Rejected — it forces an arbitrary and contestable precedence decision between a grantee's own default and its funder's, and it makes the template that produced a given file an inference rather than a recorded choice.
*Forward note*: a remembered per-budget choice is planned, but as a **client-side pre-fill of the picker**, not a server-side implicit pick. The server stays strict. This keeps the audit trail unambiguous and turns "my saved template was un-shared or deleted" into a clean 400 asking the user to choose again, instead of a silent format change on an export they assumed was routine.

**9. A template's body is a bounded renderer-options blob, not a layout description.**
The blob names the renderer plus options over it: which sheets to include, whether the donor-currency estimate column is shown, per-column header label overrides, and whether the audit footer is shown. It is validated against a Pydantic schema on write, so an unknown key is rejected at the API rather than silently ignored at render time.
*Alternative considered*: the full declarative JSON layout engine (region map + semantic formula anchors + named styles). Deferred to its own change. The prerequisite is a golden characterization test over today's output — a cell-by-cell snapshot (value, number format, bold, fill, border) across the edge cases this code already handles: no categories, a category with zero lines, unset `estimated_exchange_rate`, `extra_fields` present and absent, null currency. Without that oracle there is no way to demonstrate the engine reproduces the current format exactly, so building the engine first would be building blind.

**10. The system default is a seeded row, not a special case in code.**
Migration seeds one `export_templates` row (`owner_customer_id` NULL, `visibility` effectively global) whose options reproduce today's output exactly. `generate_budget_export_workbook` therefore always runs against a template — existing tests keep passing because the seeded options are the current behaviour. There is exactly one rendering path, and the default is continuously exercised by every export.

**11. The template that produced a workbook is recorded in the workbook itself, not in a new table.**
`_audit_line()` already writes "Generated by OpenGrantFlow · <user> · <timestamp>"; it gains the template name and version. Templates are versioned (an edit bumps `version`), so a file exported last quarter stays explicable after its template is edited.
*Alternative considered*: an `export_history` table recording every generated file. Rejected as scope creep — nothing currently needs to enumerate past exports, and the footer answers the question the audit trail actually asks.

**12. Sheet-writing code is organized as one class per sheet, sharing a `_SheetWriter` base — a code-organization decision, orthogonal to Decision 9's template-options axis.**
Group 1's Sheet 1 implementation threads the same handful of values (`ws`, `plan`, `cols`, `local_fmt`, `estimate_fmt`, `has_rate`) through five-plus free functions; Sheets 2 and 3 land with the same shape of state. `_SheetWriter` holds the shared cell-writing helpers (`_bold_row`, `_set_cell`, `_apply_box_border`, currency formatting) as methods; `OriginalBudgetSheet`, `DashboardSheet`, `ExpenseListSheet` each subclass it with a `write()` entry point. `generate_budget_export_workbook` stays a thin dispatcher choosing which sheet classes to instantiate — group 6's template-driven sheet subset (Decision 9) selects among these same fixed classes, it does not introduce new ones per template.
*Alternative considered*: one class per donor-selectable template (each a bespoke layout), inheriting a shared parent. Rejected — same trap as Decision 9's declarative-engine alternative: unbounded, hard to review, and duplicates the single-rendering-path guarantee Decision 10 exists to give. Templates still only vary bounded options over a fixed, closed set of sheet renderers.
*Timing*: introduced in group 2 (converting Sheet 1's free functions into `OriginalBudgetSheet` alongside building `DashboardSheet`), not group 1. A base class guessed from one caller is unproven; group 2 gives two real sheets to validate what's actually shared before group 3 adds a third.

## Risks / Trade-offs

- [A budget with many report lines/allocations could make generation slow] → Out of scope for a "simple export" of one budget; single-budget expense volume in practice is small (tens to low hundreds of lines), revisit only if real usage shows otherwise.
- [`estimated_exchange_rate` unset on an older or draft budget leaves Sheet 1's donor-currency column and Sheet 2's deviation column blank for that budget] → Matches existing GrandFlow convention (donor dashboard already excludes rather than fabricates); the export's local-currency figures are still fully populated.
- [Category subtotal rows in Sheet 2 need the same rollup as Sheet 1's category grouping] → Reuse the same category-grouping logic/order between Sheet 1 and Sheet 2 rather than deriving it twice, to avoid the two sheets silently disagreeing on category order or membership.
- [A grantee's remembered template is later un-shared, deleted, or its donor relationship revoked] → The strict server (Decision 8) turns this into a 400 that names the problem and asks for a new selection, rather than silently exporting a different format. The picker must surface that message inline, not as a generic failure.
- [The options blob is a schema that will grow, and old rows will lag it] → Validate on write against a versioned Pydantic schema and treat every option as optional-with-a-default at render time, so a row written before an option existed still renders. Adding an option must never require a data migration.
- [Renderer options interact with Sheets 2/3, which are not built yet] → The sheet-subset option is specified now but only becomes meaningful once groups 2 and 3 land; group 6 depends on them for that reason. Until then the option validates but has a single legal value.
