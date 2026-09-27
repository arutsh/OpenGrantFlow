## MODIFIED Requirements

### Requirement: Superuser can deactivate any company
A `superuser` SHALL be able to deactivate (soft-delete) any company when acting with their own `superuser` role directly (no impersonation session). Through an impersonation session, a superuser SHALL be able to deactivate only the company that session is scoped to. A company's own `admin`, acting without an active impersonation session, SHALL NOT be able to deactivate their own company.

#### Scenario: Superuser deactivates a company directly
- **WHEN** a superuser with no impersonation session requests deactivation of any company by `customer_id`
- **THEN** the company is marked deactivated and its users can no longer authenticate

#### Scenario: Superuser deactivates a company while impersonating it
- **WHEN** a superuser impersonating a target company requests deactivation of that same company
- **THEN** the request succeeds

#### Scenario: Impersonation session cannot deactivate a different company
- **WHEN** a superuser impersonating company A requests deactivation of company B
- **THEN** the request is rejected as forbidden and B remains active

#### Scenario: Company's own admin cannot deactivate their own company
- **WHEN** a user with `role: admin`, not impersonating, requests deactivation of their own company
- **THEN** the system rejects the request as unauthorized

#### Scenario: Deactivated company's users cannot log in
- **WHEN** a user belonging to a deactivated company attempts to authenticate
- **THEN** the system rejects the login attempt

#### Scenario: Deactivation does not retroactively revoke already-issued tokens
- **WHEN** a user of a deactivated company holds an access token issued before deactivation and still unexpired
- **THEN** services other than login continue to honor that token until it expires naturally — cross-service enforcement is out of scope for this change
