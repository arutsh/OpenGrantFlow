## ADDED Requirements

### Requirement: Impersonation tokens are bounded by their effective role and tenant
Authorization for every write under an impersonation token SHALL be decided from the token's effective claims (`role: admin`, the impersonated `customer_id`), never from the real actor's stored role. An impersonation token SHALL NOT act on any user or company outside the impersonated customer. Actions SHALL still be attributed to the superuser's real identity.

#### Scenario: Impersonating A cannot modify a user in B
- **WHEN** a superuser impersonating company A calls any users-service write endpoint targeting a user of company B
- **THEN** the request is rejected as forbidden

#### Scenario: Stored superuser role does not widen an impersonation token
- **WHEN** a request carries an impersonation token whose `user_id` belongs to a superuser in the database
- **THEN** the request is authorized exactly as an admin of the impersonated company, with no superuser-only branch applied
