## Why

Once Tiers 1–4 close the current gap, coverage will only stay complete if every *future* model also inherits `AuditMixin`/`AuditColumnsMixin` — and nothing today would catch a new model that skips it, since the original 17-model gap accumulated silently over time with no test ever failing. The repo already has a precedent for this class of guard (`test_celery_task_registration.py` catches worker task modules missing from Celery's include-list the same way) — this change applies the same pattern to model audit coverage.

## What Changes

- Add a test per service (`ai`, `budget`, `chat`, `users`) that walks every class inheriting from that service's `Base` and asserts it also inherits `AuditMixin` or `AuditColumnsMixin`.
- Maintain an explicit, per-service exemption list (e.g. append-only logs where `updated_by` doesn't apply are still required to have `created_by` via one of the mixins — true exemptions are only for genuinely non-auditable tables, expected to be small: e.g. pure association/junction tables with no independent lifecycle, if any exist after Tiers 1-4 land).
- Failing the guard test requires either adding the mixin to the new model or adding it to the exemption list with a comment stating why — makes "skip the audit trail" a deliberate, reviewable choice instead of a silent default.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `model-audit-trail`: adds the requirement that coverage is enforced automatically for all current and future models, with exemptions required to be explicit.

## Impact

- New test file per service, e.g. `services/{ai,budget,chat,users}/tests/test_audit_mixin_coverage.py` (or equivalent existing conftest/test-discovery location per service).
- No production code changes — this is test-only.
- Depends on Tiers 1–4 (`audit-mixin-auto-population`, `audit-mixin-rollout-tier3`, `audit-mixin-rollout-tier4`) having landed first, so the guard starts from a fully-covered baseline rather than immediately failing on pre-existing gaps.
