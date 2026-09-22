One task group = one GitHub ticket = one PR, merged before the next group starts.

## 1. Coverage guard tests — depends on audit-mixin-auto-population, audit-mixin-rollout-tier3, audit-mixin-rollout-tier4 all being merged

- [x] 1.1 Confirm the full model inventory is at 100% `AuditMixin`/`AuditColumnsMixin` coverage post-Tier 4 (re-run the original survey); identify any remaining genuine exemptions.
- [x] 1.2 Add `services/ai/tests/test_audit_mixin_coverage.py`: walk `Base.registry.mappers`, assert each mapped class inherits `AuditMixin`/`AuditColumnsMixin` or is in a documented exemption set.
- [x] 1.3 Add the equivalent test in `services/budget/tests/`.
- [x] 1.4 Add the equivalent test in `services/chat/tests/`.
- [x] 1.5 Add the equivalent test in `services/users/tests/`.
- [x] 1.6 Verify each guard test fails as expected when a temporary non-compliant model is added locally (sanity-check the assertion actually catches the failure mode, then remove the temporary model).
- [ ] 1.7 Run all 4 services' test suites clean; PR merged.
