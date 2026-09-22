## Why

`BudgetModel.status` (`ai_draft`/`draft`/`confirmed`/`archived`) is a plain field with no transition history: there's no way to answer "was this budget ever confirmed before it was archived," and no `AuditLog`-style table exists for budget mutations (only `services/ai` has one). Status is mutated via a generic PATCH-style path (`budget_crud.py`, `budget.status = status or budget.status`) with no record of who changed it or when. The identical need has now surfaced independently in a second domain: admin/superuser actions (invite user, remove user, update company, deactivate company) in `admin-management-page`, which today logs nothing for a company admin acting within their own tenant (only impersonation sessions get `privileged_access_logs` coverage). Two independent domains wanting the same shape (actor/target/from→to/timestamp) is a strong signal this should be one general mechanism, not a budget-only table.

## What Changes

- Add a general-purpose transition/action audit-log table (or `shared/db/` mixin), not scoped to budgets specifically — shape: actor, target entity/id, from-state, to-state, changed_at.
- Wire budget status transitions (`budget_crud.py`'s status-update choke point) through this mechanism.
- Wire admin-management actions (invite, remove, promote/demote, deactivate) through the same mechanism, including company-admin-acting-within-own-tenant (not just superuser impersonation, which already has separate `privileged_access_logs` coverage).
- Design the table to double as the source of truth for "was this budget ever confirmed" (needed by the donor dashboard's grantee status breakdown), rather than adding a separate `confirmed_at` high-water-mark column later.
- Decide whether an intermediate `submitted` status (grantee → donor handoff, discussed but not yet added to `BudgetStatus`) belongs in this same piece of work, since it would be another transition the table needs to capture.

## Capabilities

### New Capabilities
- `transition-audit-log`: general actor/target/from→to/timestamp audit trail, applied to budget status transitions and admin-management actions.

## Status

Proposal only — scope and design (single shared table vs. per-domain tables via a common mixin, exact schema, whether `submitted` status is in scope) need deeper investigation before task breakdown. Parent tracking: [GitHub issue #138](https://github.com/arutsh/GrantFlow/issues/138).

**Dependency note:** two audit-infrastructure changes are already in flight and this should sequence behind both, not run in parallel:
- `shared-feat-307-audit-mixin-rollout-tier4` (current branch) — finishing it first avoids context-switching mid-audit-buildout and any incidental conflict in `shared/db/`.
- `async-privileged-access-audit` (active, 0/9 tasks done) — makes `log_privileged_access`/`PrivilegedAccessSink` async and removes the per-service dedicated sync engine each service was hand-copying for audit writes. This new transition-audit-log's write path should reuse that same async sink pattern once it lands, rather than becoming a 5th hand-duplicated audit-write mechanism (see `[[project_privileged_access_log_model_duplication]]`).
