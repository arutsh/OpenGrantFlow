## Why

5 models have no `created_at`/`updated_at`/`created_by`/`updated_by` at all, including the two most central entities in the system: `UserModel` and `CustomerModel`. There is currently no way to answer "when was this user account created" or "who created this organization" — a real audit-trail gap on the core entities, not just a peripheral one. With `audit-mixin-auto-population` providing automatic, CRUD-code-free population, this is the last tier needed for full coverage — but it's also the highest-risk tier since `UserModel`/`CustomerModel` sit on the auth/tenancy hot path.

## What Changes

- Add full `AuditMixin` (`created_at`/`updated_at`/`created_by`/`updated_by`) to: `AIProvider`, `AIProviderModel` (service `ai`, catalog/seed tables), `DonorTemplateModel` (service `budget`), `CustomerModel`, `UserModel` (service `users`).
- For `CustomerModel`/`UserModel`: `created_by` will typically be `NULL` for self-registration flows (no authenticated actor exists yet at account-creation time) and populated for admin-created accounts (e.g. company-onboarding, admin-invite flows) — this is expected, not a defect.
- Alembic migration per affected service (`ai`, `budget`, `users`) adding nullable columns — no backfill.
- **BREAKING**: none — additive, nullable columns.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `model-audit-trail`: extends automatic-population coverage to the last 5 models, including the two core entities `UserModel`/`CustomerModel`; documents that `created_by` is expected to be `NULL` for unauthenticated self-registration flows.

## Impact

- Model files: `services/ai/app/models/{ai_provider.py, ai_provider_model.py}`, `services/budget/app/models/mapping.py` (`DonorTemplateModel`), `services/users/app/models/{customer.py, user.py}`.
- New Alembic migration in `ai`, `budget`, `users`.
- `UserModel`/`CustomerModel` are touched by auth (login, registration, JWT issuance), company-onboarding, and admin-management flows with a large existing test surface — needs staging verification before merge, per this repo's standard practice for auth-adjacent schema changes.
- Depends on `audit-mixin-auto-population` being implemented first.
