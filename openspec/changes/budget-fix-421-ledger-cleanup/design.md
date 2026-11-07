## Context

`services/budget/app/services/budget_services.py`'s `update_budget_service` handles "Cancel Confirmation" (revert `confirmed` → `draft`) in its `is_reverting` block (~L234-248): it rejects the revert if any report is non-draft, then deletes every draft report belonging to the budget. It never queries or touches `FundingReceiptModel`/`CurrencyConversionModel` (`services/budget/app/models/currency_ledger.py`), which are FK'd to `budgets.id` with no `ON DELETE CASCADE`. Result: after a revert + currency/rate edit + re-confirm, stale ledger rows from the old configuration keep displaying with no way to remove or correct them — `record_receipt_service`/`record_conversion_service` (`currency_ledger_services.py`) only support create, never update or delete.

Separately, `delete_budget_service` (budget_services.py:427-441) already refuses a hard delete via a caught `IntegrityError` when ledger rows exist, proving the FK relationship is real — but that guard is only reachable on `DELETE /budgets/{id}`, never on the revert path, since revert never deletes the `BudgetModel` row.

## Goals / Non-Goals

**Goals:**
- Make "Cancel Confirmation" refuse to run while the budget has any ledger movement, instead of silently orphaning it.
- Give the owner a way to actually resolve that block: either fix individual mistaken entries (typo in an amount/date) or wipe the ledger outright and start over.
- Keep the FIFO allocation trail (`budget-currency-ledger`'s existing requirements) internally consistent — never let an edit/delete leave an allocation record pointing at a conversion whose amounts no longer match what was actually allocated.

**Non-Goals:**
- No soft-delete or history table for deleted/edited ledger entries. The budget service has no audit-log table for this domain (only `created_by`/`updated_by` columns); a status-history table is a separately tracked backlog item, not scoped here. Reset/delete/edit are hard operations, consistent with how report deletion already works on revert.
- No in-place edit of a currency conversion that already has allocations against it. Splitting/re-deriving allocations across an amount change on a partially-consumed lot is materially more complex (would need to re-run FIFO for every report line downstream of it) and isn't needed to fix the reported bug — the reset-everything path covers it.
- No change to how funding receipts/conversions are created, or to the FIFO/backfill algorithms themselves.

## Decisions

**1. Revert guard: block on *any* ledger row, not just "unconsumed" ones.**
`is_reverting` gets a check (query `list_funding_receipts`/`list_currency_conversions` for the budget) that raises `DomainError` if either list is non-empty, mirroring the existing message shape used by `delete_budget_service` ("Budget cannot be [reverted] while it has existing funding receipts or currency conversions"). Rejecting on presence rather than trying to distinguish "safe" from "unsafe" ledger rows keeps the rule simple and matches the user's framing: any real-money movement means the owner must explicitly deal with it before the budget config can change out from under it.

*Alternative considered*: only block if a conversion has allocations (i.e., money has actually been spent against it), allowing receipts/unconsumed conversions to be silently discarded on revert. Rejected — silently discarding a recorded bank conversion on revert is exactly the "dangling" behavior being fixed; it should never happen without the owner explicitly choosing it (via Reset Ledger).

**2. "Reset Ledger" is a single bulk endpoint, not client-side looped deletes.**
One `POST /budgets/{id}/ledger/reset` (or equivalent service call) deletes all of a budget's `FundingReceiptModel` and `CurrencyConversionModel` rows (allocations cascade via existing `report_lines`/model relationships — see Risks) in one transaction. A confirmation dialog on the frontend is the only guard; the backend performs it unconditionally for the owner. This avoids partial-failure states from looping individual deletes client-side and gives one clear audit point (a single log line / one place to eventually hook a future audit table).

**3. Funding receipts: always editable/deletable by the owner.**
Nothing else references a `FundingReceiptModel` row (no allocation table points at it), so update/delete are unconditional CRUD operations, gated only by ownership — matching `record_receipt_service`'s existing `_get_owned_budget` check.

**4. Currency conversions: editable/deletable only when they have zero allocations.**
Both `_backfill_unsatisfied_expenses` (new conversion backfilling old unsatisfied expenses) and `allocate_fifo_service` (new report line consuming lots) create rows in `ReportLineConversionAllocationModel` keyed by `conversion_id`. A conversion with zero allocation rows has never funded any expense — directly or via backfill — so changing or removing it can't invalidate any existing allocation. The update/delete service functions query allocations for the conversion first and raise `DomainError` if any exist, pointing the owner at Reset Ledger or at editing/removing the report lines that consumed it.

*Alternative considered*: allow edit only (not delete) when allocations exist, re-running FIFO for every downstream report line. Rejected as unnecessary complexity for a case the reset path already handles, and riskier — a rate correction on a heavily-consumed old lot could silently reshuffle allocations across many historical report lines.

**5. No new schema/migration.**
All new operations are CRUD against the two existing tables; `ReportLineConversionAllocationModel` deletion on conversion delete/reset relies on either an explicit delete-then-delete in the service layer or a DB-level cascade added via a small migration if it doesn't already cascade — confirm the current FK (`services/budget/migrations/versions/000007_add_currency_ledger.py`) before implementation; add `ondelete="CASCADE"` there only if needed, otherwise delete allocation rows explicitly in the reset/delete service function ahead of the conversion delete.

**6. Money types follow `budget-fix-341-money-integrity`, which lands first.**
New update schemas for receipts and conversions use the shared `Money` type (`Decimal` in Python, JSON number on the wire), not `float`. The zero-allocation check in Decision 4 and any balance comparison use exact `Decimal(0)`, never the removed `FLOAT_EPSILON`. See that change's design.md, Decisions 1 and 4.

## Risks / Trade-offs

- **[Risk] Reset Ledger is destructive and irreversible with no undo.** → Mitigation: owner-only, explicit confirm-dialog on the frontend ("this permanently deletes N receipts and M conversions"), and it's opt-in — the revert block never triggers it automatically.
- **[Risk] Blocking revert on any ledger row could strand a budget** that legitimately needs to go back to draft for an unrelated reason (e.g. wrong duration) but also has real ledger history the owner doesn't want to lose. → Mitigation: this is the intended trade-off per the bug report — the owner must consciously choose to reset before reverting; there is no destructive default. If this proves too strict in practice it can be revisited once real usage patterns are observed.
- **[Risk] Race between "check allocations are zero" and "delete/edit conversion"** if a report line is created concurrently. → Mitigation: reuse the existing `budget_ledger_lock` advisory lock (already serializes ledger-mutating operations per budget) around the new update/delete/reset service functions, same pattern as `record_conversion_service`.
- **[Trade-off] No partial ledger cleanup UI (e.g. "delete just conversions, keep receipts")** — Reset Ledger is all-or-nothing. Individual delete/edit already covers the surgical case; Reset Ledger is deliberately the blunt instrument for "just let me start over."

## Migration Plan

No data migration required. Deploy order: backend CRUD/service/route additions and the revert guard first, then frontend actions. The revert guard is a pure behavior tightening (previously-silent data loss now becomes a blocked action), safe to ship ahead of the frontend having a way to resolve it — worst case an owner briefly sees a revert rejected with no in-app remediation until the frontend ships, which is strictly safer than today's silent orphaning.

## Open Questions

- Confirm whether `report_line_conversion_allocations.conversion_id` FK currently cascades on delete at the DB level (migration `000007_add_currency_ledger.py`); if not, the reset/delete service functions must delete allocation rows explicitly before deleting the conversion.
