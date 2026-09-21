# Spec Delta

## Purpose

Defines how an advisory CI check gets promoted to a required, merge-blocking check, and how GitHub branch protection on `main` enforces that gate so compliance controls cannot be silently bypassed by any author, human or AI.

## ADDED Requirements

### Requirement: Documented promotion criteria
The project SHALL maintain a written, measurable criterion for promoting a CI check from advisory to required (e.g. a minimum advisory period and a maximum false-positive rate observed over that period).

#### Scenario: A check meets the documented criterion
- **WHEN** an advisory check has run for the documented minimum period with a false-positive rate at or below the documented threshold
- **THEN** the check is eligible to be promoted to a required status check

### Requirement: Required status checks block merge to main
Once a check is promoted, GitHub branch protection on `main` SHALL require it to pass before a pull request can be merged.

#### Scenario: A required check fails
- **WHEN** a pull request targeting `main` has a failing required status check
- **THEN** the merge button is disabled until the check passes or an approved waiver is recorded

### Requirement: No silent bypass of required checks
Required checks SHALL NOT be bypassable via force-push or administrator merge override without an explicit, recorded waiver.

#### Scenario: Merge attempted without a waiver
- **WHEN** a pull request with a failing required check is merged without a recorded waiver
- **THEN** the merge is rejected by branch protection settings

### Requirement: Documented waiver process
The project SHALL document a waiver process for exempting a specific pull request from a required check, including who may approve the waiver and where it is recorded.

#### Scenario: A required check produces a confirmed false positive
- **WHEN** a required check fails on a finding confirmed to be a false positive
- **THEN** the documented waiver process is followed and the approval is recorded before the pull request merges

### Requirement: Required-check inventory stays current
The documented required-check list SHALL be kept current as checks from other changes land — including the dependency-vulnerability scan and the AuditMixin coverage guard tests — not only the checks introduced directly by this change.

#### Scenario: A dependency from another change lands
- **WHEN** a check originating from a different change (e.g. the Dependabot scan or the AuditMixin coverage guard) is merged and ready for promotion
- **THEN** the required-check documentation and branch protection configuration are updated to include it
