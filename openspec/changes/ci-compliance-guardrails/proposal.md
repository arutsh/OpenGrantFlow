# Proposal

## Why

Compliance-relevant code quality (secret handling, injection risk, PII in logs, missing tenant scoping) today depends entirely on the author — human or AI agent — remembering to apply it; nothing in CI catches a violation, and prompt-based guidance (e.g. CLAUDE.md rules) is not a control an auditor can point to. This change adds CI-enforced scanning that fires regardless of who or what wrote the code, is not bypassable by omission, and gives ISO 27001/GDPR posture something durable to stand on.

## What Changes

- Add gitleaks secret scanning: a new repo-root `.pre-commit-config.yaml` for local feedback, plus a CI job across all 6 service workflows and the frontend workflow (pre-commit alone is bypassable with `--no-verify`; CI is the real gate).
- Add Bandit to each Python service's existing lint step (alongside `black`/`mypy`/`flake8`) for SAST coverage of common Python security bugs.
- Add Semgrep with a custom ruleset for GDPR-relevant anti-patterns not caught by generic SAST: PII-shaped values (email, token, password, ssn) passed to logger calls, raw SQL string interpolation, and ORM queries missing tenant/`customer_id` scoping.
- Run all new checks in advisory mode first (report findings as CI annotations, do not fail the build); document explicit, measurable promotion criteria (e.g. a bounded false-positive rate over N PRs) for flipping each check to required.
- Enable GitHub branch protection on `main` requiring the promoted checks to pass before merge. This is the layer that makes every check — the new ones here, plus the Dependabot scan from `gdpr-iso27001-priority-2` and the AuditMixin coverage guard from `audit-mixin-coverage-guard` once those land — actually non-bypassable rather than advisory.
- Document the required-check list and promotion/waiver process in `docs/`.

## Capabilities

### New Capabilities
- `ci-security-scanning`: secret scanning (gitleaks) and SAST (Bandit, Semgrep custom rules) running per-service in CI, advisory-first with a defined path to required.
- `branch-protection-enforcement`: required GitHub status checks on `main`, the criteria for promoting an advisory check to required, and the waiver process for an exception.

### Modified Capabilities
(none — additive only, no existing spec's requirements change)

## Impact

- `.github/workflows/{budget,chat,ai,users,worker,frontend,e2e}.yml` and `shared.yml`: new scan steps.
- New `.pre-commit-config.yaml` at repo root (none exists today).
- New `.semgrep/` custom rules directory.
- New `docs/security/ci-compliance-guardrails.md` documenting the required-check list, promotion criteria, and waiver process.
- GitHub repository settings: branch protection rule on `main` (configuration, not code, but in scope for this change).
- Depends on `gdpr-iso27001-priority-2` and `audit-mixin-coverage-guard` for two of the checks eventually added to the required list; this change's own checks (secrets, SAST) are independent and can land first.

