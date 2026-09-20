## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Append-only models never populate updated_by
A model that has no update code path (append-only: rows are only ever inserted, never modified) SHALL leave `updated_by` permanently `NULL`, since there is no update event to attribute to a user.

#### Scenario: Append-only row is never updated
- **WHEN** an append-only model's row (e.g. `AIAuditLog`, `PrivilegedAccessLog`) is queried at any time after creation
- **THEN** its `updated_by` remains `NULL`, and no code path exists that would set it
