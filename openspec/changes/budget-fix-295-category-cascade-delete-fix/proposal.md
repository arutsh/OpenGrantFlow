# Proposal

## Why

`DELETE /api/v1/budgets/{id}` returns a 400 ("Budget cannot be deleted while it has existing reports, funding receipts, or currency conversions") for budgets that have none of those, whenever a budget line was ever created and later deleted on that budget. This blocks legitimate budget deletion and was caught by the `auth-budget-chain` e2e spec's DELETE-budget step in CI, but it is a real product bug, not a test bug — any grantee who adds then removes a line before deleting a draft budget hits it.

## What Changes

- `BudgetModel.categories` gets `cascade="all, delete-orphan", passive_deletes=True` so SQLAlchemy defers to the database's existing `ON DELETE CASCADE` on `budget_categories.budget_id` instead of lazy-loading the collection and nulling out each child's non-nullable `budget_id` during flush (which raises the spurious `IntegrityError`), and deletes the children itself if the collection happens to be loaded (see design.md).
- The `minio` service in `docker-compose.local.yml` and `docker-compose.dev.yml` switches from `quay.io/minio/minio:latest` to the pinned community build `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`. MinIO stopped publishing public images (quay.io now returns 401, Docker Hub's `minio/minio` returns 404), so a fresh CI runner can't start the e2e stack — without this, the `E2E Tests` workflow can't verify the fix above.
- Out of scope: cleaning up an orphaned category when its last line is deleted is a separate, pre-existing bookkeeping gap (also related to the already-known global-category-namespace issue) and is not needed to fix this bug — the cascade settings make budget deletion correct regardless of whether an orphaned category row exists.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this restores compliance with the already-declared `async-persistence` requirement ("No lazy-load MissingGreenlet risk": every relationship a route/service reads SHALL be explicitly eager-loaded or never accessed outside an awaited context, and no request path SHALL trigger an implicit lazy-load) and the `budget-categories` requirement that every category belongs to exactly one budget without ever becoming a dangling reference; it does not change either requirement's text.

## Impact

- `services/budget/app/models/budget.py` (`BudgetModel.categories` relationship)
- Fixes `DELETE /api/v1/budgets/{id}` for any budget that ever had a line added and removed
- `docker-compose.local.yml`, `docker-compose.dev.yml` (`minio` service image only; `command`, env, volumes and healthcheck unchanged)
- Unblocks `frontend-typescript/e2e/specs/api/auth-budget-chain.spec.ts` in the `E2E Tests` CI workflow, which currently fails at image pull on every branch, `main` included
