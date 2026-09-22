# model-audit-trail Specification

## Purpose
Automatic, request-scoped population of `created_by`/`updated_by` audit columns for any model using `AuditMixin`/`AuditColumnsMixin`, via a ContextVar + SQLAlchemy event listener, applied consistently across all 4 services.

## Requirements

### Requirement: Automatic created_by population on insert
When a new row is inserted for any model using `AuditMixin` or `AuditColumnsMixin`, the system SHALL set `created_by` to the id of the currently authenticated user, without requiring the inserting CRUD code to pass it explicitly. This applies uniformly to mutable and append-only models alike.

#### Scenario: Authenticated request creates an audited row
- **WHEN** an authenticated user makes a request that inserts a new row for a model using `AuditMixin`/`AuditColumnsMixin`
- **THEN** the persisted row's `created_by` equals that user's id

#### Scenario: Insert with no authenticated request context
- **WHEN** a row is inserted for a model using `AuditMixin`/`AuditColumnsMixin` from a context with no authenticated user (e.g. a Celery worker task or a seed script)
- **THEN** the persisted row's `created_by` is `NULL` and no exception is raised

#### Scenario: Append-only log row is created
- **WHEN** an authenticated user's action results in a new row for an append-only model (e.g. `AIAuditLog`, `PrivilegedAccessLog`)
- **THEN** the persisted row's `created_by` equals that user's id, the same as for mutable models

### Requirement: Automatic updated_by population on insert and update
When a row for a model using `AuditMixin`/`AuditColumnsMixin` is inserted or updated, the system SHALL set `updated_by` to the id of the currently authenticated user, without requiring the CRUD code to pass it explicitly.

#### Scenario: Authenticated request updates an audited row
- **WHEN** an authenticated user (different from the original creator) makes a request that updates an existing row for a model using `AuditMixin`/`AuditColumnsMixin`
- **THEN** the persisted row's `updated_by` equals the updating user's id, distinct from `created_by`

#### Scenario: Authenticated request creates an audited row
- **WHEN** an authenticated user creates a new row for a model using `AuditMixin`/`AuditColumnsMixin`
- **THEN** the persisted row's `updated_by` equals that user's id, matching `created_by`

### Requirement: Non-id primary keys can use audit columns
A model whose primary key is not named `id` SHALL be able to gain `created_at`/`updated_at`/`created_by`/`updated_by` behavior via a mixin that does not declare a primary key column.

#### Scenario: Model with a custom primary key adopts the audit columns
- **WHEN** a model declares its own primary key column and mixes in the PK-less audit columns mixin
- **THEN** the model gains `created_at`, `updated_at`, `created_by`, and `updated_by` columns with the same automatic population behavior as `AuditMixin`, without a conflicting second primary key definition

### Requirement: No cross-service foreign key on audit columns
The `created_by`/`updated_by` columns SHALL remain plain UUID columns with no foreign-key constraint by default, since most adopters' actor (user) records live in a separate service/database. A model whose actor table lives in the same database MAY opt into a foreign-key constraint on `created_by`/`updated_by` referencing that table's `id` column, with `ON DELETE SET NULL`.

#### Scenario: Referenced user no longer exists
- **WHEN** a row's `created_by` or `updated_by` references a user id that has since been deleted from the users service, for a model whose table lives in a different database than the users table
- **THEN** no database constraint violation occurs, since no foreign key exists between services

#### Scenario: Same-database adopter opts into an actor foreign key
- **WHEN** a model shares a database with its actor table (e.g. `CustomerModel`/`UserModel` in the users service) and opts into the foreign-key constraint
- **THEN** `created_by`/`updated_by` are declared as foreign keys to that table's `id` column with `ON DELETE SET NULL`, so deleting the referenced actor sets the column to `NULL` rather than raising a constraint violation

### Requirement: Append-only models never populate updated_by
A model that has no update code path (append-only: rows are only ever inserted, never modified) SHALL leave `updated_by` permanently `NULL`, since there is no update event to attribute to a user.

#### Scenario: Append-only row is never updated
- **WHEN** an append-only model's row (e.g. `AIAuditLog`, `PrivilegedAccessLog`) is queried at any time after creation
- **THEN** its `updated_by` remains `NULL`, and no code path exists that would set it

### Requirement: created_by may be NULL for unauthenticated self-service creation
For models representing entities that can be created via a self-service flow with no prior authenticated user (e.g. account self-registration, self-service organization creation), the system SHALL allow `created_by` to remain `NULL` rather than requiring a non-NULL actor.

#### Scenario: User self-registers
- **WHEN** a new user account is created via the public self-registration flow (no authenticated request context)
- **THEN** the persisted `UserModel` row has `created_by` equal to `NULL`, and this is not treated as an error or a missing-data condition

#### Scenario: Admin creates an account on behalf of another user
- **WHEN** an authenticated admin user creates a user or customer account through an admin-management flow
- **THEN** the persisted row's `created_by` equals the admin's user id, since an authenticated actor exists at creation time

### Requirement: Automated enforcement of audit-mixin coverage
Each service's test suite SHALL include a test that enumerates every SQLAlchemy model mapped against that service's declarative `Base` and asserts each one inherits `AuditMixin` or `AuditColumnsMixin`, unless explicitly exempted with a documented reason.

#### Scenario: New model omits the audit mixin
- **WHEN** a new model class is added to a service's `Base` registry without inheriting `AuditMixin` or `AuditColumnsMixin`, and is not present in that service's exemption list
- **THEN** the service's test suite fails, naming the offending model class

#### Scenario: New model correctly inherits the mixin
- **WHEN** a new model class is added to a service's `Base` registry and inherits `AuditMixin` or `AuditColumnsMixin`
- **THEN** the coverage guard test passes for that model

#### Scenario: Model is deliberately exempted
- **WHEN** a model is added to a service's coverage-guard exemption list with a documented reason (e.g. a pure association table with no independent lifecycle)
- **THEN** the coverage guard test passes for that model despite it not inheriting the mixin
