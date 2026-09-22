## Context

The 5 Tier 4 models each already declare their own `id` primary key column. `AuditMixin` also declares an `id` column. In SQLAlchemy declarative mixins, an attribute defined directly on the concrete model class takes precedence over the same-named attribute inherited from a mixin — so mixing in `AuditMixin` on these models does **not** require touching their existing `id` definitions; only the unset `created_at`/`updated_at`/`created_by`/`updated_by` attributes get pulled in from the mixin. This significantly de-risks adopting `AuditMixin` on `UserModel`/`CustomerModel`: no PK change, no id-format migration.

`UserModel`/`CustomerModel` sit on the auth/tenancy hot path (login, registration, JWT issuance, company onboarding, admin management) with a large existing test surface — this is the highest-risk tier of the whole rollout, ordered last deliberately.

## Goals / Non-Goals

**Goals:**
- All 5 remaining models gain full audit columns with correct automatic population.
- Zero change to existing `id` PK definitions or values on any model.
- No behavior change to auth/registration flows beyond the new columns being populated.

**Non-Goals:**
- No backfill of `created_at` for existing users/customers (historical creation time is genuinely unknown).
- No change to how `UserModel.id`/`CustomerModel.id` are generated — both already use `uuid.uuid4()` directly, same as `AuditMixin`'s default, so there's nothing to reconcile.
- No requirement that `created_by` be non-NULL — self-registration has no authenticated actor, so NULL is a valid, expected value here (unlike, say, budget models where every row has a clear creator).

## Decisions

**1. Adopt `AuditMixin` directly on all 5 models — rely on SQLAlchemy's mixin-attribute-override behavior rather than restructuring existing `id` columns.**
Confirmed via SQLAlchemy declarative semantics: a class-level attribute always wins over a mixin's same-named attribute. Alternative considered: renaming/removing each model's own `id` and adopting the mixin's — rejected as unnecessary churn and risk on the auth hot path for zero behavioral benefit.

**2. `created_by`/`updated_by` on `UserModel`/`CustomerModel` are allowed to be `NULL` for self-service flows.**
Self-registration and self-service org creation have no prior authenticated user to attribute the row to. This is expected and documented (see spec delta), not treated as a gap to work around (e.g. no synthetic "system" user id).

**3. Migrate `ai`, `budget`, `users` independently; `AIProvider`/`AIProviderModel` (catalog tables, likely seeded via migration/admin scripts rather than end-user requests) may show `NULL` `created_by` even for legitimate inserts.**
Acceptable — these are reference data, not user-attributable domain rows in the same sense.

## Risks / Trade-offs

- **[Risk]** `UserModel`/`CustomerModel` are read/written by a large number of existing call sites and tests; adding columns via `AuditMixin` could interact unexpectedly with code that does `SELECT *`-style comparisons, serialization schemas that don't allowlist fields, or ORM query construction that assumes the current column set. → **Mitigation**: staging verification required before merge (per this repo's standard practice for auth-adjacent schema changes); run the full `users` service test suite and manually verify login/registration/admin flows.
- **[Risk]** `created_by`/`updated_by` being `NULL` for the majority of `UserModel`/`CustomerModel` rows (self-registration is the common path) could be mistaken for "the feature isn't working" during review. → **Mitigation**: explicitly document expected-NULL cases in the spec delta and in code comments at the relevant CRUD sites.
- **[Trade-off]** Not backfilling `created_at` for existing rows means historical users/customers show `NULL` for "when created" indefinitely — accepted since the true value is unrecoverable.

## Migration Plan

Standard Alembic migration per service (`ai`, `budget`, `users`), additive/nullable columns only, no backfill. This tier ships last in the overall rollout, after Tiers 1–3 have validated the automatic-population mechanism in lower-risk services. Rollback = standard Alembic downgrade; no data loss since nothing is backfilled or removed.

## Open Questions

- ~~Should admin-created accounts (company-onboarding, admin-invite flows) be audited to confirm they already pass an actor context that would populate `created_by` correctly, or do those flows also run unauthenticated in some cases?~~
  **Resolved:** both `POST /users/invite` and `POST /customers/` require `Depends(get_validated_user)` (`services/users/app/api/user_routes.py:265`, `services/users/app/api/customer_routes.py:36`), which sets the actor contextvar (`shared/security/dependencies.py:54`) before the row is inserted — covered by `TestAdminInviteAuditTrail`/`TestCustomerCreationAuditTrail` in `test_tier4_audit_columns.py`. "Company-onboarding" (a new company's founder self-registering) goes through the unauthenticated self-registration path instead, where `created_by` staying `NULL` is the documented, tested (`TestUserSelfRegistrationAuditTrail`), expected behavior per decision 2 above — not a gap.
