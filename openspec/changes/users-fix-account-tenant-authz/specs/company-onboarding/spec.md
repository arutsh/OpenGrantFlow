## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Joining an existing company does not change role
**Reason**: Letting a user attach themselves to any existing company by `customer_id` is an unauthorized-membership hole. It was never used by the frontend, which only sends `new_customer_name`.
**Migration**: Existing companies take on new members through admin invitations (`company-user-administration`). Superusers use impersonation or the planned `superuser-admin-console` endpoints.
