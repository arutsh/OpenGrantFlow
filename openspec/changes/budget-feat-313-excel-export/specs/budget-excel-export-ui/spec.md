# Spec Delta

## Purpose

Gives a budget owner or funder viewer a visible way to choose an export template, trigger the single-budget Excel export, and download it from the budget detail view — and gives an organisation a place to manage and share its own templates.

## ADDED Requirements

### Requirement: Export action on budget detail view
The frontend SHALL show an "Export to Excel" action on the single-budget detail view, visible to anyone with read access to that budget (owner or funder), that downloads the generated workbook via `GET /budgets/{budget_id}/export.xlsx`.

#### Scenario: Owner triggers export
- **WHEN** the budget owner clicks "Export to Excel" on their budget's detail view
- **THEN** the frontend requests the export endpoint and saves the returned file with a filename derived from the budget's name

#### Scenario: Export unavailable to unauthorized viewers
- **WHEN** a user without read access to the budget views a page that would otherwise show the button
- **THEN** the frontend does not show the "Export to Excel" action

### Requirement: Export failure feedback
The frontend SHALL show an inline error, without navigating away from the budget detail view, when the export request fails.

#### Scenario: Backend error surfaced
- **WHEN** the export endpoint returns an error
- **THEN** the frontend shows an inline error message and the user remains on the budget detail view

### Requirement: Template picker before export
When more than one export template is available for a budget, the frontend SHALL require the viewer to choose one before the export request is sent, showing each option's source (the built-in default, the viewer's own organisation, or the budget's funder). When only one template is available, the frontend SHALL export directly without prompting.

#### Scenario: Multiple templates available
- **WHEN** a viewer with access to more than one template clicks "Export to Excel"
- **THEN** the frontend presents the available templates, labelled by source, and sends the export request only once one is chosen

#### Scenario: Only the default available
- **WHEN** a viewer has access to no templates beyond the built-in default
- **THEN** clicking "Export to Excel" starts the download immediately, with no picker shown

#### Scenario: Chosen template no longer available
- **WHEN** the export is rejected because the chosen template has been deleted or un-shared
- **THEN** the frontend shows that reason inline and reopens the picker with the current options, rather than showing a generic failure

### Requirement: Template management view
The frontend SHALL provide a view where an organisation's authorised users can create, rename, edit, and delete that organisation's own export templates, and set each one's visibility to either private or shared with the organisation's grantees. The built-in default SHALL be shown as read-only.

#### Scenario: Donor shares a template with its grantees
- **WHEN** a donor's authorised user sets one of their templates to shared with grantees
- **THEN** that template becomes selectable by the NGOs that donor funds, on budgets the donor funds

#### Scenario: Another organisation's templates are not listed
- **WHEN** a user opens the template management view
- **THEN** only their own organisation's templates and the read-only built-in default are listed, with no template owned by any other organisation shown or editable

#### Scenario: Built-in default is read-only
- **WHEN** a user views the built-in default template in the management view
- **THEN** it is displayed without edit or delete controls

#### Scenario: Duplicate name rejected inline
- **WHEN** a user saves a template using a name their organisation already uses
- **THEN** the frontend shows the validation error inline on the form without losing the entered values
