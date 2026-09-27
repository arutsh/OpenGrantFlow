# auth-hardening Specification

## Purpose
TBD - created by archiving change gdpr-iso27001-priority-1. Update Purpose after archive.

## Requirements

### Requirement: Password Complexity Policy
The system SHALL enforce a minimum password strength (minimum length, not entirely numeric, not identical to the account's email or name) on registration and on any password change. Registration attempts SHALL also be subject to per-source-IP rate limiting, independent of password strength validation.

#### Scenario: Registration with weak password
- **WHEN** a registration request is submitted with a password that does not meet the minimum strength policy
- **THEN** the system rejects the registration with a validation error explaining the policy

#### Scenario: Registration rejects client-supplied role even with a valid password
- **WHEN** a registration request has a strong, policy-compliant password but also includes a `role` field set to `admin` or `superuser`
- **THEN** the system creates the account successfully, but with `role: user`, ignoring the supplied `role`

### Requirement: Login Rate Limiting
The system SHALL limit the rate of failed login attempts per account and per source IP, and SHALL temporarily lock out further attempts once a threshold is exceeded.

#### Scenario: Repeated failed login attempts
- **WHEN** an account receives more failed login attempts than the configured threshold within the configured window
- **THEN** the system rejects further login attempts for that account until the lockout window elapses, even if correct credentials are supplied

### Requirement: Registration Cannot Set Privileged Role
The system SHALL ignore any `role` value supplied by the client on `POST /api/register` and SHALL always create the new account with role `user`. Elevation to `admin` or `superuser` SHALL only be possible through the `company-onboarding` promotion path or the protected admin-management endpoints, never through registration. Since registration no longer returns a session, this SHALL be verified against the persisted account record and, once available, the role claim of the session issued at successful email verification — not against a token returned by registration itself.

#### Scenario: Client attempts to self-register as superuser
- **WHEN** an unauthenticated caller submits `POST /api/register` with `"role": "superuser"` (or any value other than `user`) in the request body
- **THEN** the account is created with `role: user`, and the session subsequently issued at successful email verification carries a `role` claim of `user`

#### Scenario: Client attempts to self-register as admin
- **WHEN** an unauthenticated caller submits `POST /api/register` with `"role": "admin"` in the request body
- **THEN** the account is created with `role: user`, and the session subsequently issued at successful email verification carries a `role` claim of `user`

### Requirement: Resend-Verification Rate Limiting
The system SHALL limit the rate of resend-verification requests per combined email+source-IP key, using the same lockout mechanism applied to login and registration, matching the existing `auth-hardening` rate-limiting pattern.

#### Scenario: Repeated resend requests from one source
- **WHEN** a combined email+source-IP key submits more resend-verification requests than the configured threshold within the configured window
- **THEN** the system rejects further resend requests for that key with a 429 response until the lockout window elapses

### Requirement: Role Column Is Constrained At The Database Level
The `users.role` column SHALL be constrained by a database CHECK constraint (or equivalent) to only accept the values defined by the `UserRole` enum (`superuser`, `admin`, `user`), independent of any application-layer validation.

#### Scenario: Direct write of an invalid role is rejected by the database
- **WHEN** any code path attempts to persist a `role` value outside `superuser`/`admin`/`user` on a `users` row
- **THEN** the database rejects the write with a constraint violation

### Requirement: Registration Rate Limiting
The system SHALL limit the rate of registration attempts per source IP, using the same lockout mechanism applied to login, matching the existing `auth-hardening` rate-limiting pattern.

#### Scenario: Repeated registration attempts from one source
- **WHEN** a single source IP submits more registration attempts than the configured threshold within the configured window
- **THEN** the system rejects further registration attempts from that source with a 429 response until the lockout window elapses

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
