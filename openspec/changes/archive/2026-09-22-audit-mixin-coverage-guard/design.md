## Context

By the time this change ships, Tiers 1–4 will have brought every current model to full `AuditMixin`/`AuditColumnsMixin` coverage. The risk from here forward is drift: a new model added later, in any of the 4 services, that simply forgets to inherit the mixin — exactly how the original 17-model gap accumulated, with no test ever failing along the way. `services/worker`'s `test_celery_task_registration.py` already solves the analogous problem for Celery task modules (a task module not added to the explicit `include=[]` list silently never loads) by walking the actual registered set and diffing it against what's on disk/expected. This change applies the same enumerate-and-assert pattern to models.

## Goals / Non-Goals

**Goals:**
- Any new model in any of the 4 services that doesn't inherit `AuditMixin`/`AuditColumnsMixin` fails a test, with a clear message pointing at the offending class.
- Genuine exemptions (if any survive after Tiers 1–4) are explicit, named, and require a reason — not a silent default.

**Non-Goals:**
- No CI/lint-level enforcement beyond the test suite (a failing pytest test is enough, matching the Celery guard's precedent).
- No attempt to enforce this for models outside `services/{ai,budget,chat,users}` (e.g. no models currently exist in `services/worker`).

## Decisions

**1. One guard test per service, not one repo-wide test.**
Each service has its own `Base`/module tree and its own test suite/CI job; a per-service test fails fast in the PR for the service that introduced the gap, and mirrors how the Celery guard is scoped to the worker service.

**2. Discover models via `Base.registry.mappers` (or equivalent SQLAlchemy introspection), not filesystem/import-path scanning.**
Walking the declarative registry guarantees every mapped class is seen regardless of which module it lives in, and avoids maintaining a parallel "list of model files" that itself could drift out of date.

**3. Exemption list is a literal set of class names/paths in the test file itself, each with an inline one-line reason.**
Keeps the exemption visible right next to the assertion that would otherwise fail, rather than in a separate config file that's easy to forget about. Expected to start empty or near-empty once Tiers 1–4 land; if a genuinely non-auditable model type emerges later (e.g. a pure many-to-many association table with no independent lifecycle), it gets added here with justification.

## Risks / Trade-offs

- **[Risk]** If Tiers 1–4 don't fully land before this guard ships, the guard immediately fails on the remaining gap. → **Mitigation**: explicit dependency ordering (this change proposed last, only implemented after the others merge).
- **[Trade-off]** A per-service test means 4 near-identical test files rather than one shared implementation — acceptable given each service's `Base`/registry is genuinely separate (no shared code to factor the check into without adding a new shared test-utility dependency for a 4-line check).

## Migration Plan

No production code or schema change — test-only addition, one PR per service (or one combined PR if all 4 are trivial enough to review together; see tasks.md). No rollback concerns beyond reverting the test file if it produces false positives.

## Open Questions

- Should the guard also assert `updated_by` is *never* set for models explicitly marked append-only (formalizing the Tier 3 append-only distinction), or is that better left to the per-model tests added in Tier 3?
