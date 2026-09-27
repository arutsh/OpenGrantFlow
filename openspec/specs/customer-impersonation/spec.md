# customer-impersonation Specification

## Purpose
TBD - created by archiving change superuser-cross-tenant-access. Update Purpose after archive.

## Requirements

### Requirement: Superuser starts an impersonation session for any customer
The system SHALL allow a caller with the `superuser` role to request a time-boxed impersonation token scoped to any target `customer_id`, without needing that customer's credentials. The resulting token SHALL grant admin-equivalent permissions for the target customer.

#### Scenario: Superuser starts impersonating a customer
- **WHEN** a superuser requests an impersonation token for a target `customer_id`
- **THEN** the system issues a token scoped to that customer with admin-equivalent permissions, and the request is logged per the `privileged-access-audit` capability

#### Scenario: Non-superuser cannot start an impersonation session
- **WHEN** a caller without the `superuser` role requests an impersonation token
- **THEN** the system rejects the request

#### Scenario: Superuser can switch target customer at any time
- **WHEN** a superuser who already holds one impersonation token requests a new one for a different `customer_id`
- **THEN** the system issues a new token scoped to the new target, independent of any prior impersonation token

### Requirement: Impersonation token preserves the superuser's real identity
The impersonation token SHALL carry the superuser's own real user identity, not an identity borrowed from any existing user of the target customer. Actions performed using the token SHALL be attributed to the superuser's real identity wherever the system records who performed an action.

#### Scenario: A write made during impersonation is attributed to the superuser
- **WHEN** a superuser, while impersonating a customer, performs an action that the system records with an actor/creator field
- **THEN** that field reflects the superuser's own real identity, not any identity belonging to the target customer

### Requirement: Impersonation tokens are time-boxed
The system SHALL issue impersonation tokens with a limited lifetime; a token SHALL stop granting access once it expires.

#### Scenario: Expired impersonation token is rejected
- **WHEN** a request is made using an impersonation token past its expiry
- **THEN** the system rejects the request

### Requirement: Superuser has no cross-tenant data access outside an active impersonation session
A caller with the `superuser` role but no active impersonation session (no `customer_id` resolved on their token) SHALL NOT receive another customer's data through any endpoint. List endpoints SHALL return an empty result and single-resource endpoints SHALL behave as not-found, rather than falling back to returning data across all customers. Impersonation SHALL be the only channel through which a superuser accesses customer data; no endpoint SHALL grant a blanket bypass based on the `superuser` role alone.

#### Scenario: Superuser without an active session lists a resource
- **WHEN** a superuser with no active impersonation session requests a list of budgets, reports, or other customer-owned resources
- **THEN** the system returns an empty result, not the resources of every customer

#### Scenario: Superuser without an active session requests a specific resource
- **WHEN** a superuser with no active impersonation session requests a specific customer's resource by id
- **THEN** the system responds as if the resource does not exist

#### Scenario: Superuser with an active session sees exactly the impersonated customer's data
- **WHEN** a superuser has an active impersonation session for a target customer
- **THEN** the system scopes their requests to that customer exactly as it would for that customer's own user, with no special-casing based on the `superuser` role

### Requirement: Superuser selects a customer to impersonate from the top bar
The application SHALL provide a customer-search control in the top navigation bar, visible only to users with the `superuser` role, allowing them to search for and select any customer to begin an impersonation session.

#### Scenario: Superuser searches for a customer to impersonate
- **WHEN** a superuser opens the customer-search control and types a customer name
- **THEN** the system shows matching customers, and selecting one starts an impersonation session for that customer

#### Scenario: Non-superuser does not see the control
- **WHEN** a user without the `superuser` role views the top bar
- **THEN** the customer-search control is not present

### Requirement: Active impersonation shows a persistent, non-dismissible warning banner
Whenever a superuser has an active impersonation session, the application SHALL display a persistent, high-visibility warning banner stating that the current view is a superuser impersonation session and naming the customer being viewed. The banner SHALL remain visible across navigation while the session is active, and SHALL NOT offer any way to hide or dismiss it other than exiting the impersonation session.

#### Scenario: Banner appears immediately on starting impersonation
- **WHEN** a superuser selects a customer from the picker and impersonation begins
- **THEN** the warning banner is displayed immediately, naming the impersonated customer

#### Scenario: Banner persists across navigation
- **WHEN** a superuser navigates between pages while impersonating
- **THEN** the warning banner remains visible on every page

#### Scenario: Banner cannot be dismissed without ending the session
- **WHEN** a superuser is impersonating a customer
- **THEN** the application provides no control to hide the banner that does not also end the impersonation session

#### Scenario: Exiting impersonation removes the banner and restores the superuser's own session
- **WHEN** a superuser uses the banner's exit control
- **THEN** the impersonation session ends, the banner disappears, and the superuser returns to their own normal session

### Requirement: Impersonation tokens are bounded by their effective role and tenant
Authorization for every write under an impersonation token SHALL be decided from the token's effective claims (`role: admin`, the impersonated `customer_id`), never from the real actor's stored role. An impersonation token SHALL NOT act on any user or company outside the impersonated customer. Actions SHALL still be attributed to the superuser's real identity.

#### Scenario: Impersonating A cannot modify a user in B
- **WHEN** a superuser impersonating company A calls any users-service write endpoint targeting a user of company B
- **THEN** the request is rejected as forbidden

#### Scenario: Stored superuser role does not widen an impersonation token
- **WHEN** a request carries an impersonation token whose `user_id` belongs to a superuser in the database
- **THEN** the request is authorized exactly as an admin of the impersonated company, with no superuser-only branch applied
