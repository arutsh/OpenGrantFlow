## ADDED Requirements

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
