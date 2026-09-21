# Design

## Context

Six independently path-filtered GitHub Actions workflows (`ai`, `budget`, `chat`, `users`, `worker`, `frontend`, plus `shared` and `e2e`) each run `black`/`mypy`/`flake8` then `pytest` for Python services (see `.github/workflows/budget.yml` for the reference shape). No pre-commit hooks and no security tooling exist today. Root `pyproject.toml` only configures `black`. See proposal.md - Why for the motivation.

## Goals / Non-Goals

**Goals:**
- Every new scan is enforced by CI, not by an agent or developer remembering a rule.
- Advisory rollout is observable: findings are visible per-PR, and there's a documented, low-ceremony way to tell when a check is ready to become required.
- The eventual required-check list composes cleanly with checks landing from other changes (`gdpr-iso27001-priority-2`'s Dependabot scan, `audit-mixin-coverage-guard`'s guard tests) without this change needing to touch those changes' code.

**Non-Goals:**
- Not building the Dependabot config or the AuditMixin guard tests themselves — those belong to their own changes; this change only accounts for them in the required-check inventory once they exist.
- Not covering the frontend's TypeScript/JS-specific SAST needs beyond secret scanning — `npm audit` is already scoped separately in `gdpr-iso27001-priority-2`.
- Not attempting perfect precision on the custom Semgrep tenant-scoping rule in this change — see Risks below.

## Decisions

**gitleaks over trufflehog for secret scanning.** Both are viable; gitleaks has a simpler single-binary GitHub Action, a pre-commit hook maintained upstream, and a smaller default ruleset that's easier to tune for this repo's `.env.*-secrets` file patterns. TruffleHog's verification-against-live-API feature is more useful at much larger scale than this repo needs.

**Bandit for Python SAST, not a broader multi-language SAST suite.** All backend services are Python/FastAPI; Bandit integrates directly into the existing per-service lint step with no new infra. A heavier tool (e.g. Snyk Code) is deferred — it would duplicate Semgrep's role here and adds a vendor dependency this change doesn't need.

**Semgrep for the custom GDPR rules, not hand-written pytest guard tests.** The AuditMixin coverage guard (a separate change) uses pytest because it needs SQLAlchemy model-registry introspection. The PII-logging, raw-SQL, and tenant-scoping checks are pattern-matches over source text/AST across arbitrary files, which is exactly Semgrep's use case, and its rules are declarative YAML reviewable independent of the codebase. Custom rules live in `.semgrep/rules/*.yml`, one file per rule family, run via `semgrep --config .semgrep/`.

**Advisory mode implemented as `continue-on-error: true` on each new job, not a separate non-blocking workflow.** Keeping advisory checks in the same workflow file as the eventual required version means promoting a check is a one-line diff (remove the flag), not a workflow restructure. Findings still post as CI annotations and appear in the PR checks list, just don't block merge.

**Pilot on `budget` service first, then roll out to the rest.** Matches how AuditMixin tiers were rolled out incrementally rather than all-at-once. `budget` is chosen because it has the most active CI usage right now, giving the fastest signal on false-positive rate.

**Branch protection changes are a manual GitHub settings step, not code.** GitHub branch protection rules aren't stored in-repo (no Terraform/IaC for repo settings exists in this project). Tasks.md will call out the exact settings to change and who needs admin access to change them.

## Risks / Trade-offs

- **[Risk]** The tenant/`customer_id`-scoping Semgrep rule is the highest false-positive-risk rule in this set — many legitimate queries (lookups by primary key, superuser/admin paths already reviewed under `customer-impersonation`) don't include tenant scoping and shouldn't. → **Mitigation**: ship this specific rule with a narrower initial pattern (only flag queries against an explicit list of known multi-tenant tables) and treat it as the last rule promoted to required, after the longest advisory period.
- **[Risk]** Secret scanning against full git history (not just the diff) could surface pre-existing leaked secrets that need rotation, not just a CI failure to fix. → **Mitigation**: scope the initial gitleaks CI job to the PR diff only; run a one-time full-history scan separately (task in tasks.md) so any historical findings are triaged deliberately, not discovered mid-PR.
- **[Risk]** Advisory-mode checks that nobody looks at provide no real signal for promotion. → **Mitigation**: tasks.md includes a step to track findings per check (e.g. a running count in the PR template or a weekly export) so the promotion criteria in the `branch-protection-enforcement` spec has real data behind it, not a guess.
- **[Trade-off]** Running Bandit/Semgrep/gitleaks adds CI time to every PR. → Accepted: these are fast static tools (seconds, not minutes) relative to the existing test suite; not mitigated further in this change.

## Migration Plan

1. Add gitleaks pre-commit hook + CI job (diff-scoped) to `budget` service only; advisory.
2. Add Bandit to `budget`'s lint step; advisory.
3. Add Semgrep with the PII-logging and raw-SQL rules to `budget`; advisory. Tenant-scoping rule follows once the other two show acceptable false-positive rates.
4. Roll the same three additions out to `chat`, `ai`, `users`, `worker`, `shared`, `frontend`, `e2e` workflows.
5. Run the one-time full-history gitleaks scan; triage any findings (rotate/redact) before treating secret scanning as trustworthy.
6. Document promotion criteria and the required-check inventory in `docs/security/ci-compliance-guardrails.md`.
7. Once each check's advisory period and false-positive threshold are met, remove `continue-on-error` and add it to `main`'s required status checks in GitHub repo settings.
8. Repeat step 7 as `gdpr-iso27001-priority-2` (Dependabot) and `audit-mixin-coverage-guard` land, updating the same doc.

Rollback: each check is independently removable by deleting its CI step (advisory) or unchecking it in branch protection (required) — no data migration or schema involved, so rollback is low-risk at any stage.
