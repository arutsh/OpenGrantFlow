## MODIFIED Requirements

### Requirement: No cross-service foreign key on audit columns
The `created_by`/`updated_by` columns SHALL remain plain UUID columns with no foreign-key constraint by default, since most adopters' actor (user) records live in a separate service/database. A model whose actor table lives in the same database MAY opt into a foreign-key constraint on `created_by`/`updated_by` referencing that table's `id` column, with `ON DELETE SET NULL`.

#### Scenario: Referenced user no longer exists
- **WHEN** a row's `created_by` or `updated_by` references a user id that has since been deleted from the users service, for a model whose table lives in a different database than the users table
- **THEN** no database constraint violation occurs, since no foreign key exists between services

#### Scenario: Same-database adopter opts into an actor foreign key
- **WHEN** a model shares a database with its actor table (e.g. `CustomerModel`/`UserModel` in the users service) and opts into the foreign-key constraint
- **THEN** `created_by`/`updated_by` are declared as foreign keys to that table's `id` column with `ON DELETE SET NULL`, so deleting the referenced actor sets the column to `NULL` rather than raising a constraint violation

## ADDED Requirements

### Requirement: created_by may be NULL for unauthenticated self-service creation
For models representing entities that can be created via a self-service flow with no prior authenticated user (e.g. account self-registration, self-service organization creation), the system SHALL allow `created_by` to remain `NULL` rather than requiring a non-NULL actor.

#### Scenario: User self-registers
- **WHEN** a new user account is created via the public self-registration flow (no authenticated request context)
- **THEN** the persisted `UserModel` row has `created_by` equal to `NULL`, and this is not treated as an error or a missing-data condition

#### Scenario: Admin creates an account on behalf of another user
- **WHEN** an authenticated admin user creates a user or customer account through an admin-management flow
- **THEN** the persisted row's `created_by` equals the admin's user id, since an authenticated actor exists at creation time
