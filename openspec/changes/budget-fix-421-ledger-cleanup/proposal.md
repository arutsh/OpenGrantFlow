## Why

Reverting a confirmed budget to draft ("Cancel Confirmation") deletes the budget's reports but silently leaves any recorded funding receipts and currency conversions in place — they're keyed only by `budget_id` with no cascade. If the owner then edits the budget's currency/exchange-rate setup and re-confirms, the old ledger rows (denominated in the prior currency configuration) keep displaying alongside the new one, with no way to tell they're stale or to remove them. Separately, there is currently no way to fix a mistyped amount or date on a funding receipt or conversion at all — the only lever is a full budget revert, which is both too broad and (per the bug above) doesn't even clean up the thing it's supposed to fix.

## What Changes

- Block "Cancel Confirmation" (revert confirmed → draft) when the budget has any funding receipt or currency conversion recorded, with an error directing the owner to clean up the ledger first.
- Add a "Reset Ledger" bulk action that deletes all of a budget's funding receipts and currency conversions (and their report-line allocations) in one explicit, confirmed step, as the fast path to unblock a revert without deleting entries one by one.
- Add update and delete for individual funding receipts (amount, received date) — no downstream dependents, so always allowed on an owned budget.
- Add update and delete for individual currency conversions (donor amount, local amount, converted date), but only when the conversion has zero report-line allocations against it; a conversion that has already funded expense allocations must be cleared of those allocations first (via "Reset Ledger" or by editing/removing the report lines that consumed it) before it can be edited or deleted directly. **BREAKING**: none — these are net-new endpoints/actions.
- Frontend: per-row Edit/Delete actions on the funding-receipt and conversion history list, and a "Reset Ledger" action in the currency ledger section, all owner-only.

## Capabilities

### New Capabilities
(none — this extends existing ledger and confirmation capabilities)

### Modified Capabilities
- `budget-currency-ledger`: adds update/delete for funding receipts, update/delete for currency conversions (guarded by allocation state), and a bulk reset operation that clears a budget's entire ledger.
- `budget-currency-ledger-ui`: adds per-row edit/delete controls to the receipt/conversion history and a "Reset Ledger" action.
- `budget-confirmation-ui`: the revert-to-draft ("Cancel Confirmation") transition now also rejects when the budget has any funding receipt or currency conversion, in addition to the existing non-draft-report rejection.

## Impact

- Backend: `services/budget/app/crud/funding_receipt_crud.py`, `services/budget/app/crud/currency_conversion_crud.py` (update/delete queries), `services/budget/app/services/currency_ledger_services.py` (update/delete/reset services + allocation-state guard), `services/budget/app/api/funding_receipt_routes.py`, `services/budget/app/api/currency_conversion_routes.py` (new routes), `services/budget/app/services/budget_services.py` (revert guard at the `is_reverting` block).
- Frontend: currency-ledger section component(s) that render funding-receipt/conversion history (owner-only edit/delete + reset action), matching `frontend-typescript` conventions used by `budget-currency-ledger-ui`.
- Nginx/gateway route wiring for any new endpoints (all three gateway configs, per prior experience on this repo).
- No schema/migration changes expected — no new tables or columns, only new CRUD operations against existing `funding_receipts` and `currency_conversions` tables.
