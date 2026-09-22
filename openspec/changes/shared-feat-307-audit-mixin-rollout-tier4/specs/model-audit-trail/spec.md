## ADDED Requirements

### Requirement: created_by may be NULL for unauthenticated self-service creation
For models representing entities that can be created via a self-service flow with no prior authenticated user (e.g. account self-registration, self-service organization creation), the system SHALL allow `created_by` to remain `NULL` rather than requiring a non-NULL actor.

#### Scenario: User self-registers
- **WHEN** a new user account is created via the public self-registration flow (no authenticated request context)
- **THEN** the persisted `UserModel` row has `created_by` equal to `NULL`, and this is not treated as an error or a missing-data condition

#### Scenario: Admin creates an account on behalf of another user
- **WHEN** an authenticated admin user creates a user or customer account through an admin-management flow
- **THEN** the persisted row's `created_by` equals the admin's user id, since an authenticated actor exists at creation time
