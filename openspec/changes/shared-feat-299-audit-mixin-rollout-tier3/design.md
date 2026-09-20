## Context

`audit-mixin-auto-population` establishes the mechanism (ContextVar + SQLAlchemy event listener) so that adding `AuditMixin`/`AuditColumnsMixin` to a model is sufficient on its own — no CRUD code needs to change. This change applies that mechanism to the 11 models that already track their own timestamps but lack `created_by`/`updated_by`, spread across `ai`, `chat`, `budget`, and `users`, each with an independent Alembic history.

Two structural wrinkles from the original investigation apply here:
- `CustomerAiDefaults` (PK `customer_id`) and `UserProfileModel` (PK `user_id`) need `AuditColumnsMixin` (no PK), not `AuditMixin`.
- `PrivilegedAccessLog` is duplicated identically 4× (one class per service) — pre-existing hygiene issue, out of scope to dedupe here, but each copy needs the same column addition independently since they're 4 separate classes/tables.

## Goals / Non-Goals

**Goals:**
- All 11 Tier 3 models gain `created_by`/`updated_by` and correctly populate them via the existing automatic mechanism.
- Preserve existing `created_at` semantics where a model already has one (don't rename/change existing columns).
- Explicitly decide, per model, whether `updated_by` is semantically meaningful (append-only logs: no) rather than adding it uniformly without thought.

**Non-Goals:**
- No dedup of the 4 `PrivilegedAccessLog` copies into a shared base class.
- No change to `UserProfileModel`'s cache-sync mechanism.
- No retroactive backfill — existing rows get `NULL` `created_by`/`updated_by`.

## Decisions

**1. Append-only models (`AIAuditLog`, `PrivilegedAccessLog` ×4) get `created_by` only — no update path is added, `updated_by` stays permanently `NULL`.**
These models intentionally have no `update_*` CRUD function (audit/log integrity depends on immutability). Adding `updated_by` would be a column that's structurally impossible to ever populate — accept it as always-`NULL`, matching the semantics of "this row was never updated," rather than removing the column from the mixin (which would require a third mixin variant).

**2. `UserProfileModel` is evaluated case-by-case, not auto-included.**
It's a read-through cache populated by cross-service sync, not user action — `created_by`/`updated_by` may reflect "which sync process wrote this" rather than a meaningful actor, or may not apply at all. Decide during implementation (task 1 of tasks.md) whether to adopt `AuditColumnsMixin` or add it to the coverage guard's exemption list instead.

**3. One Alembic migration per affected service, not a combined cross-service migration.**
Each service has its own independent migration history; `ai` touches 5 models in one migration, `chat` touches 3, `budget` touches 2, `users` touches 1 — batched per-service since they're already grouped by ticket/PR boundary in tasks.md.

## Risks / Trade-offs

- **[Risk]** Migrations add non-nullable-looking intent (audit columns) but must be nullable with no server-side default requirement, since historical rows have no known creator. → **Mitigation**: all new columns nullable, no backfill, matches the existing `AuditMixin` column definitions exactly.
- **[Risk]** `PrivilegedAccessLog`'s audit purpose overlaps conceptually with `created_by` — the log itself likely already records an actor/subject id as a domain field. Adding a generic `created_by` on top could be redundant or confusing. → **Mitigation**: check each `PrivilegedAccessLog` copy's existing fields during implementation; if an actor field already exists, `created_by` should equal it (validates the automatic mechanism) rather than being a second, possibly-divergent source of truth.
- **[Trade-off]** Splitting this into one ticket per service (per tasks.md) means the 4 `PrivilegedAccessLog` copies get 4 separate, near-identical PRs rather than one — accepted since each service's migration/review is independent and the duplication is already pre-existing.

## Migration Plan

Standard Alembic migration per service, additive/nullable columns only. Deploy order across services doesn't matter (fully independent). Rollback = standard Alembic downgrade, no data loss since no backfill occurred.

## Open Questions

- Does `UserProfileModel` get audit columns, or does it become a documented exemption in `audit-mixin-coverage-guard`? Decide during task 1 (see tasks.md).
- For each `PrivilegedAccessLog` copy, does an existing actor/subject field make `created_by` redundant, and if so should CRUD code assert they match rather than relying purely on the automatic listener?
