# company-onboarding Specification

## Purpose
TBD - created by archiving change new-company-user-admin. Update Purpose after archive.

## Requirements

### Requirement: Founder becomes admin of a newly created company
When a non-superuser completes onboarding by supplying `new_customer_name` on `PATCH /users/{user_id}/` while their account status is `pending`, the system SHALL create the new company (customer), attach the user to it, activate the account, and SHALL set the user's role to `admin` as part of the same update. The newly created company SHALL have `is_ngo` set to `true`.

#### Scenario: Onboarding with a new company name promotes the founder to admin
- **WHEN** a pending, non-superuser account submits `PATCH /users/{user_id}/` with `new_customer_name` set to a company name
- **THEN** a new company is created, the user's `customer_id` is set to it, `status` becomes `active`, and `role` becomes `admin`

#### Scenario: Refreshed token reflects the promotion
- **WHEN** the founder's client calls `/auth/refresh` after the onboarding update succeeds
- **THEN** the newly issued access token carries `role: admin`, since token refresh reads the user's current role from the database rather than reusing the prior token's claim

#### Scenario: Self-registered company defaults to NGO
- **WHEN** a pending, non-superuser account submits `PATCH /users/{user_id}/` with `new_customer_name` set to a company name
- **THEN** the newly created company has `is_ngo = true`, making it immediately discoverable in donor grantee search and eligible to receive grants, with no manual Settings change required

### Requirement: Founder's admin role is immediately usable elsewhere
Once a founder holds `role: admin`, every existing capability already gated on `admin`/`superuser` SHALL treat them as authorized, with no per-capability change required — the role promotion is the only thing that needed to happen.

#### Scenario: Founder can manage org-level AI settings right after onboarding
- **WHEN** a founder who just created their company refreshes their access token and calls an endpoint under `/ai/settings` (gated on `role in {"admin", "superuser"}` in `services/ai/app/api/settings_routes.py`)
- **THEN** the request succeeds on the strength of the `admin` role claim alone, with no change needed in the AI service

#### Scenario: Inviting other teammates is now covered by a dedicated capability
- **WHEN** a company admin wants to add a teammate to their company
- **THEN** the admin uses the invitation mechanism defined by the `company-user-administration` capability, rather than requiring a superuser to assign the teammate's `customer_id`/`role` directly

### Requirement: Promotion is scoped to admin, not superuser
The role assigned to a company founder SHALL be exactly `admin`, and the system SHALL NOT grant `superuser` through this or any other self-service onboarding path.

#### Scenario: New-company onboarding never grants superuser
- **WHEN** any non-superuser account creates a new company via `new_customer_name` during onboarding
- **THEN** the resulting role is `admin`, never `superuser`, regardless of any role value the client may have sent in the request body

### Requirement: Self-service profile edits cannot change membership, role, or status
`PATCH /users/{user_id}/` SHALL be callable only by the user identified by `user_id`. It SHALL accept only `first_name`, `last_name`, and (for founder onboarding while `pending`) `new_customer_name`. It SHALL reject requests that set `customer_id`, `role`, `status`, or `email`. A field omitted from the request SHALL leave the stored value unchanged. In particular, the user's existing `customer_id` and `role` SHALL be preserved.

#### Scenario: Profile edit preserves membership
- **WHEN** an active admin of company A submits `PATCH /users/{own_id}/` with only `first_name`
- **THEN** their `first_name` changes and their `customer_id` (A) and `role` (admin) are unchanged

#### Scenario: Admin cannot move themselves into another company
- **WHEN** an admin of company A submits `PATCH /users/{own_id}/` with `customer_id` set to company B
- **THEN** the request is rejected and the user remains an admin of A with no relationship to B

#### Scenario: User cannot self-activate or self-promote
- **WHEN** a user submits `PATCH /users/{own_id}/` with `status: active` or `role: admin`
- **THEN** the request is rejected and neither field changes

#### Scenario: No caller edits another user through the generic profile endpoint
- **WHEN** any caller, including a superuser or an impersonation token, submits `PATCH /users/{other_id}/`
- **THEN** the request is rejected as forbidden
