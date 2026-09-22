# Spec Delta

## Purpose

Gives a budget owner or funder viewer a visible way to trigger and download the single-budget Excel export from the budget detail view.

## ADDED Requirements

### Requirement: Export button on budget detail view
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
