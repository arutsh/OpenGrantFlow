# Tasks

One task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Secret scanning pilot (gitleaks) on budget + repo-wide pre-commit hook

- [ ] 1.0 Run `scripts/start-group.sh ci-compliance-guardrails 1` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 1.1 Add repo-root `.pre-commit-config.yaml` with a gitleaks hook; verify `pre-commit run --all-files` flags a locally-added test secret, then remove the test secret.
- [ ] 1.2 Add a gitleaks CI job (diff-scoped, `continue-on-error: true`) to `.github/workflows/budget.yml`; verify it runs on a test PR and reports a planted secret finding without failing the build, then remove the planted secret.
- [ ] 1.3 Run a one-time full-history gitleaks scan against the repo; record any findings in a tracked triage list and rotate/redact confirmed secrets before closing this task.
- [ ] 1.4 Run budget service tests/lint clean; PR merged.

## 2. Bandit SAST pilot on budget — depends on 1

- [ ] 2.0 Run `scripts/start-group.sh ci-compliance-guardrails 2` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 2.1 Add Bandit to budget's lint CI step (`continue-on-error: true`); verify it flags a planted insecure pattern (e.g. `eval` on untrusted input) in a throwaway commit, then remove the planted pattern.
- [ ] 2.2 Run budget service tests/lint clean; PR merged.

## 3. Semgrep custom rules (PII-in-logs, raw-SQL) pilot on budget — depends on 1

- [ ] 3.0 Run `scripts/start-group.sh ci-compliance-guardrails 3` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 3.1 Create `.semgrep/rules/pii-logging.yml`; verify it flags a planted logger call whose argument is named after a known PII category (email, ssn, password, token), then remove the planted call.
- [ ] 3.2 Create `.semgrep/rules/raw-sql-interpolation.yml`; verify it flags a planted f-string/`.format()`-built SQL query, then remove the planted query.
- [ ] 3.3 Add a Semgrep CI job (`continue-on-error: true`) to budget.yml running `.semgrep/rules/`.
- [ ] 3.4 Run budget service tests/lint clean; PR merged.

## 4. Roll out gitleaks + Bandit + Semgrep (PII/SQL rules) to remaining services — depends on 1, 2, 3

- [ ] 4.0 Run `scripts/start-group.sh ci-compliance-guardrails 4` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 4.1 Add the three advisory CI jobs to `chat.yml`, `ai.yml`, `users.yml`, `worker.yml`, `shared.yml`, `frontend.yml`, and `e2e.yml`, mirroring budget's configuration.
- [ ] 4.2 Verify each workflow completes successfully (green, findings advisory-only) on a real PR touching that service.
- [ ] 4.3 Run the full test suite across all affected services clean; PR merged.

## 5. Tenant-scoping Semgrep rule (narrow scope, all services) — depends on 4

- [ ] 5.0 Run `scripts/start-group.sh ci-compliance-guardrails 5` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 5.1 Enumerate the known multi-tenant tables/models requiring `customer_id` scoping, cross-referencing the `model-audit-trail` spec and current AuditMixin inventory.
- [ ] 5.2 Create `.semgrep/rules/tenant-scoping.yml` scoped to that table list; verify it flags a planted unscoped query against a known multi-tenant table and does not flag existing superuser/impersonation code paths (`customer-impersonation` capability), then remove the planted query.
- [ ] 5.3 Add the rule to all 8 workflows in advisory mode (`continue-on-error: true`).
- [ ] 5.4 Run the full test suite clean; PR merged.

## 6. Promotion tracking + documentation — depends on 4, 5

- [ ] 6.0 Run `scripts/start-group.sh ci-compliance-guardrails 6` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 6.1 Add a lightweight findings-tracking mechanism (e.g. a periodic export of CI annotation counts per check) so the promotion criteria has real data behind it.
- [ ] 6.2 Write `docs/security/ci-compliance-guardrails.md` documenting: each check, its advisory start date, promotion criteria, the current required-check inventory (including checks pending from `gdpr-iso27001-priority-2` and `audit-mixin-coverage-guard`), and the waiver process.
- [ ] 6.3 Run lint clean on the new docs; PR merged.

## 7. Promote checks to required + enable branch protection — depends on 6, and on each check's documented advisory period having elapsed

- [ ] 7.0 Run `scripts/start-group.sh ci-compliance-guardrails 7` to create/link this group's sub-issue and branch before starting any other work in this group.
- [ ] 7.1 Confirm each check meets its documented promotion criterion (false-positive rate, advisory duration) using the tracking data from group 6.
- [ ] 7.2 Remove `continue-on-error` from each promoted check's CI step across all workflows.
- [ ] 7.3 Enable GitHub branch protection on `main` requiring the promoted checks (repo admin action); verify a test PR with a deliberately failing check is blocked from merging, then revert the test change.
- [ ] 7.4 Update `docs/security/ci-compliance-guardrails.md`'s required-check list to reflect what's now enforced; PR merged.
