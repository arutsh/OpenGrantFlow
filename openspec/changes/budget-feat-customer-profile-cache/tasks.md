# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Local read-through customer cache

- [ ] 1.0 Run `scripts/start-group.sh budget-feat-customer-profile-cache 1` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 1.1 Add `CustomerProfileModel` (`customer_profiles` table: `customer_id` PK, `name`, `is_donor`, `is_ngo`, `cached_at`) in `services/budget/app/models/`, mirroring `UserProfileModel`'s shape, and generate the Alembic migration.
- [ ] 1.2 Change `get_customer_cached` in `services/budget/app/services/customer_client.py` to a DB-first, HTTP-fallback-and-backfill lookup mirroring `get_users_by_ids_cached` in `services/budget/app/services/user_cache.py`; drop the `lru_cache` decorator.
- [ ] 1.3 Verify existing callers (`budget_services.py`'s `local_currency` lookup, `excel_export_service.py`'s organisation/donor name lookups) work unchanged against the new function signature.
- [ ] 1.4 Add/update tests covering cache-hit, cache-miss-with-backfill, and persistence-across-a-fresh-DB-session (real test DB session, not a mock, per this repo's async-SQLAlchemy test convention) in `services/budget/tests/`.
- [ ] 1.5 Run budget service's tests and lint clean; PR merged.
