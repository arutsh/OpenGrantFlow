# Proposal

## Why

Budget service resolves customer/organisation details (name, `is_donor`, `is_ngo`) via `customer_client.get_customer_cached()`, a synchronous HTTP call to the users service wrapped only in a process-local, unbounded `lru_cache` — no persistence, no fallback, cold on every restart. This is weaker than the equivalent user-lookup path (`get_users_by_ids_cached`), which is backed by a real local table (`user_profiles`) populated via event consumption with HTTP fallback-and-backfill. Not currently a bottleneck; filed low-priority to fix the asymmetry before it becomes one (e.g. under load, or as more call sites depend on customer lookups, such as `budget-feat-313-excel-export`).

## What Changes

- Add a `customer_profiles` table in budget service (mirroring `user_profiles`' shape: `customer_id` PK, `name`, `is_donor`, `is_ngo`, `cached_at`).
- Change `get_customer_cached` (and callers in `customer_client.py`, `budget_services.py`, `excel_export_service.py`) to read this table first, falling back to HTTP on miss and writing the result back — same write-through-on-miss pattern already used by `get_users_by_ids_cached`, no new event type or publisher change required.
- No proactive invalidation for now (accepting staleness on rare customer-detail changes, consistent with current behavior); revisit only if this becomes a real problem.

## Capabilities

### New Capabilities
- `budget-customer-cache`: local read-through cache for customer/organisation details (name, `is_donor`, `is_ngo`) used by budget service, replacing the unbounded in-memory `lru_cache`.

### Modified Capabilities
(none — no existing spec currently documents `get_customer_cached`'s caching behavior)

## Impact

- Affected code: `services/budget/app/services/customer_client.py`, new `services/budget/app/models/customer_cache.py`, new Alembic migration, callers in `budget_services.py` and `excel_export_service.py`.
- No changes to users service, no new events, no new consumers.
- Low priority / not scoped in detail — revisit if the current in-memory cache becomes a measurable bottleneck.
