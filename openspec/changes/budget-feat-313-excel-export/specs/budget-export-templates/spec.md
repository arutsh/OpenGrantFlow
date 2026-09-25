# Spec Delta

## Purpose

Lets an organisation create, own, and share the export templates that `budget-excel-export`'s template selection and rendering consume — the storage, uniqueness, versioning, and access-scoping rules for those template records.

## ADDED Requirements

### Requirement: Template-scoped ownership
An export template SHALL belong to exactly one organisation and SHALL carry a visibility of either private or shared with grantees. Template names SHALL be unique within an owning organisation. Every query for templates SHALL be scoped to a requesting organisation; the system SHALL NOT expose a way to read templates without an organisational scope.

#### Scenario: Duplicate name within an organisation
- **WHEN** an organisation creates a second template with the name of one it already owns
- **THEN** the request is rejected, so which template a name refers to is never ambiguous

#### Scenario: Same name across organisations
- **WHEN** two different organisations each create a template named "Annual Report"
- **THEN** both are accepted, and each organisation only ever sees its own

### Requirement: Template versioning on edit
An export template SHALL carry a version number that advances whenever its name, visibility, or options are updated.

#### Scenario: Edit bumps version
- **WHEN** an organisation updates one of its own templates
- **THEN** the template's stored version increases, distinguishing the edited template from the one that produced any workbook exported before the edit
