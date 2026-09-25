## Why

Two "money can silently be wrong" gaps in the budget service, confirmed but deliberately not blocking prior ships:

1. **Money is stored as binary floating point.** Every money column in the budget service is `Float`: `BudgetModel.total_amount`/`donor_total_amount`/`estimated_exchange_rate`, `BudgetLineModel.amount`, `ReportLineModel.amount`, and the whole currency ledger (`FundingReceiptModel.amount`, `CurrencyConversionModel.donor_amount`/`local_amount`, `ReportLineConversionAllocationModel.amount_allocated`). The drift is already worked around in code: FIFO lot matching and the Excel export compare against `FLOAT_EPSILON = 1e-9` instead of zero.
2. **`total_amount` integrity has loose ends.** Single-line create/update/delete (`budget_line_services.py`) commit the line and then commit the recalculated total separately, so a failure between the two persists a stale total. `total_amount` is accepted on `BudgetCreate`/`BudgetUpdate` but silently dropped, and a recalculation for a missing budget returns `None` with no log.
3. **Currency codes are never validated.** `shared/services/currency_service.py` has a working ISO 4217 check, but no budget write path calls it. The frontend dropdown is a hardcoded 11-code stand-in (`frontend-typescript/src/utils/currency.ts`) because no endpoint exposes the real list.

Real money starts flowing through these tables via the currency ledger, and `ledger-budget` is about to add update/delete paths on the same columns. Both get harder to fix the longer they wait.

## What Changes

- Migrate every column listed above from `Float` to `Numeric`, with a data migration for existing rows (money and rates at different scales, see design.md).
- Introduce a shared `Money` Pydantic type: `Decimal` in Python, a plain JSON number on the wire. **API contract unchanged**, no frontend or chat/ai changes required.
- Convert float-dependent server arithmetic to `Decimal`: FIFO allocation (`FLOAT_EPSILON` tolerance → exact zero), dashboard aggregates, Excel export.
- Make single-line create/update/delete one transaction: line write and total recalculation commit together.
- Reject `total_amount` on budget input schemas (it's server-derived) instead of silently dropping it. Log when a recalculation finds no budget.
- Validate `local_currency`/`actual_currency` as ISO 4217 on budget input schemas (`BudgetCreate`, `CreateBudgetWithLinesRequest`). Ledger rows carry no currency of their own and inherit the budget's, so this covers them too.
- Expose the ISO 4217 list via a budget-service endpoint and replace the frontend's hardcoded 11-code list.

**Dropped from the earlier draft** (already fixed, or not real):
- the `create_budget_with_lines_service` rollback gap: fixed by #286, which moved to a single commit;
- the "duplicated `COALESCE(SUM)` formula": the second copy is a frozen one-off backfill in migration `000003`.

## Capabilities

### New Capabilities
- `currency-code-validation`: ISO 4217 validation on budget writes, plus a list endpoint.
- `budget-money-precision`: exact storage and arithmetic, JSON numbers on the wire.

### Modified Capabilities
- `budget-currency-ledger`: exact FIFO allocation, no epsilon.
- `donor-dashboard`: total tracking is atomic, and client-supplied `total_amount` is rejected.

## Impact

- **Schema**: one budget migration (`ALTER COLUMN ... TYPE numeric`) over 9 columns in 6 tables.
- **Code**: `shared/schemas` (budget, budget-line, report-line, currency-ledger), budget CRUD/services, `excel_export_service.py`, `dashboard_crud.py`, `currency_conversion_crud.py`.
- **Ordering**: lands before `ledger-budget` (which already depends on it) and before the remaining groups of `budget-feat-313-excel-export`.
