## ADDED Requirements

### Requirement: No anonymous account-creation path accepts privileged attributes
The system SHALL NOT expose any unauthenticated endpoint that creates a user account with a caller-supplied `role`, `status`, or company membership. `POST /api/register` SHALL be the only anonymous account-creation path, and every account it creates SHALL have role `user`, status `pending`, and no company.

#### Scenario: Legacy generic user-creation endpoint is gone
- **WHEN** an unauthenticated caller sends `POST /api/users/` with `role: superuser` and `status: active`
- **THEN** the request is rejected (the route does not exist) and no user row is created

#### Scenario: Verification never yields a privileged token for a self-created account
- **WHEN** an attacker registers an address they control, requests a verification email, and completes `POST /auth/verify-email`
- **THEN** the issued access token carries `role: user` and no `customer_id`

### Requirement: Registration ignores client-supplied company membership
`POST /api/register` SHALL NOT attach the new account to any existing company, whatever `customer_id` the request body contains. Joining an existing company SHALL only be possible through an admin invitation (`company-user-administration`) or a superuser-authorized operation.

#### Scenario: Registration with another company's id
- **WHEN** a caller registers with a body containing `customer_id` of an existing company
- **THEN** the account is created with no `customer_id`, and the token issued at verification carries no `customer_id`
