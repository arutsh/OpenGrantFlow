# Spec Delta

## Purpose

Defines the automated secret-scanning and SAST checks that run in CI against every service and the frontend, so security-relevant code properties are checked mechanically rather than relying on the author — human or AI — to remember to apply them.

## ADDED Requirements

### Requirement: Secret scanning in CI
Every pull request, regardless of target service, SHALL be scanned by an automated secret-detection tool (e.g. gitleaks) covering the full diff.

#### Scenario: PR introduces a credential-shaped string
- **WHEN** a pull request adds a string matching a known secret pattern (API key, private key, connection string with embedded credentials, etc.)
- **THEN** the CI secret-scanning job reports the finding, including file and line

#### Scenario: PR contains no secrets
- **WHEN** a pull request's diff contains no secret-shaped strings
- **THEN** the CI secret-scanning job completes with no findings

### Requirement: Local secret-scanning feedback before push
The repository SHALL provide a pre-commit hook that runs the same secret-detection tool used in CI, so a contributor sees a finding before pushing.

#### Scenario: Developer stages a credential-shaped string locally
- **WHEN** a developer runs `git commit` on a change containing a secret-shaped string
- **THEN** the pre-commit hook flags the file and line before the commit completes

### Requirement: SAST coverage for Python services
Each Python service's CI lint step SHALL include a static-analysis security scan (e.g. Bandit) covering common insecure patterns (insecure deserialization, use of `eval`/`exec` on untrusted input, weak cryptographic primitives, hardcoded bind-all network interfaces).

#### Scenario: PR introduces an insecure pattern
- **WHEN** a pull request adds code matching a known insecure pattern covered by the SAST tool
- **THEN** the CI job reports the finding with file, line, and rule identifier

### Requirement: Custom rules for GDPR-relevant anti-patterns
CI SHALL run an additional rule set (e.g. Semgrep) covering patterns not caught by generic SAST: PII-shaped values passed to logging calls, raw SQL built via string interpolation instead of parameterized queries, and ORM queries against multi-tenant tables that omit tenant/`customer_id` scoping.

#### Scenario: PII-shaped value passed to a logger
- **WHEN** a pull request adds a logging call whose argument is a variable or field named after a known PII category (email, ssn, password, token, etc.)
- **THEN** the CI job reports the finding

#### Scenario: Query on a multi-tenant table omits tenant scoping
- **WHEN** a pull request adds a database query against a table known to require tenant/`customer_id` scoping, without a filter on that column
- **THEN** the CI job reports the finding

### Requirement: Advisory-first rollout
Each check introduced by this capability SHALL run in advisory (non-blocking) mode when first introduced: findings are surfaced as CI output but do not fail the build or block merge.

#### Scenario: A newly introduced check finds an issue
- **WHEN** a check that has not yet been promoted to required finds an issue on a PR
- **THEN** the finding is visible in CI output and the PR remains mergeable on that basis alone
