## Why

Two related money-correctness gaps in the budget service, both confirmed but deliberately not blocking prior ships:

1. **`Budget.total_amount` recalculation is fragile.** From the donor-dashboard code review (#133): `create_budget_with_lines_service`'s rollback path bypasses `recalculate_budget_total` entirely (calls raw `delete_budget_line` CRUD directly, currently masked because the parent budget is deleted right after); the line write and total recalculation commit separately with no wrapping transaction; money is stored as `Float` (not `Decimal`), so binary floating-point drift is now surfaced through the API; a missed recalculation is silently swallowed with no log; `total_amount` is client-writable on `BudgetCreate`/`BudgetUpdate` but silently dropped; the `COALESCE(SUM(amount), 0)` formula is implemented twice (migration backfill SQL + SQLAlchemy) with no single source of truth. **The `Float` problem is wider than `total_amount` alone** — a repo-wide check found the same `Float` type on `BudgetLineModel.amount`, `ReportLine.amount` (`report.py`), and the entire currency-ledger table set (`currency_ledger.py`: `FundingReceipt.amount`, `CurrencyConversion.donor_amount`/`local_amount`, `CurrencyConversionAllocation.amount_allocated`) — every money column in the budget service is `Float`.
2. **Currency codes are never validated.** `shared/services/currency_service.py` has a working ISO 4217 module (`validate_currency`, `get_currency_list`, etc.) re-exported by both budget and users utils, but no actual call site validates `Budget.actual_currency`/`local_currency` or the currency-ledger's `record_receipt_service`/`record_conversion_service` inputs. The frontend currency dropdown is a hardcoded 11-code stand-in (`frontend-typescript/src/utils/currency.ts`) for the same reason — no endpoint exposes the real list.

Bundled together because both are "money can silently be wrong" gaps in the same service, even though they're different mechanisms (recalculation integrity vs. input validation) — real money starts flowing through this table via the currency ledger, so both get harder to fix the longer they wait.

## What Changes

- Fix the rollback-path gap: route `create_budget_with_lines_service`'s exception handlers through `recalculate_budget_total` (or a CRUD-layer/ORM event listener so no future line-mutation path can skip it), not raw `delete_budget_line`.
- Wrap line-write + recalculation in a single transaction so a second-commit failure can't leave a stale total persisted.
- Migrate all budget-service money columns from `Float` to `Decimal`/`Numeric` — `budget.py` (`BudgetModel`, `BudgetLineModel`), `report.py` (`ReportLine.amount`), `currency_ledger.py` (`FundingReceipt.amount`, `CurrencyConversion.donor_amount`/`local_amount`, `CurrencyConversionAllocation.amount_allocated`) — including a data migration for existing rows. Doing this before the active `ledger-budget` change adds more update/delete surface on these same currency-ledger columns avoids compounding the Float-drift problem in new code.
- Either enforce or reject `total_amount` on `BudgetCreate`/`BudgetUpdate` instead of silently dropping it; log when a recalculation is skipped (budget not found).
- De-duplicate the `COALESCE(SUM(amount), 0)` formula to one source of truth.
- Wire `validate_currency()` into `update_budget_service` (`actual_currency`/`local_currency`) and into `record_receipt_service`/`record_conversion_service`.
- Expose `get_currency_list()` via a small endpoint (budget or users service) so the frontend dropdown can replace its hardcoded 11-code stand-in with the real ISO 4217 list.

## Capabilities

### New Capabilities
- `currency-code-validation`: server-side rejection of invalid ISO 4217 currency codes on budget and currency-ledger writes.

## Status

Proposal only — no design.md/tasks.md yet. Recommend investigating the `Float`→`Decimal` migration path (data migration for existing rows) before task breakdown, since it's the piece most likely to get harder the longer it waits.

**Dependency note:** `currency_ledger_services.py` (`record_receipt_service`/`record_conversion_service`) is also touched by the active, not-yet-started `ledger-budget` change (adds update/delete for funding receipts and currency conversions on the same file). No hard blocker either order, but landing this change first — schema types and validation in place before more code is added against `Float` columns — avoids rework in `ledger-budget` and a same-file merge conflict if both are in flight at once.
