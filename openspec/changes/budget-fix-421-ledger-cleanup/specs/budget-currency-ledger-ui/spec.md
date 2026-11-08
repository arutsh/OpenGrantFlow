## ADDED Requirements

### Requirement: Edit or delete a funding receipt from the history list
The frontend SHALL show Edit and Delete actions on each funding receipt in the ledger history, visible to the budget owner only, and SHALL apply the change via the backend's funding-receipt update/delete endpoints.

#### Scenario: Edit a receipt
- **WHEN** the owner edits a funding receipt's amount or received date and saves
- **THEN** the frontend sends an update request and, on success, reflects the corrected values in the displayed history

#### Scenario: Delete a receipt
- **WHEN** the owner deletes a funding receipt from the history list
- **THEN** the frontend sends a delete request and, on success, removes it from the displayed history and updates the balance figures

#### Scenario: Receipt actions hidden from the funder
- **WHEN** the current user is the budget's matching funder, not its owner
- **THEN** the ledger history shows funding receipts without Edit or Delete actions

### Requirement: Edit or delete a currency conversion from the history list
The frontend SHALL show Edit and Delete actions on each currency conversion in the ledger history, visible to the budget owner only, and SHALL surface the backend's rejection message when a conversion has already funded an expense and cannot be directly edited or deleted.

#### Scenario: Edit an unallocated conversion
- **WHEN** the owner edits a currency conversion's donor amount, local amount, or converted date and saves, and the backend accepts the change
- **THEN** the frontend reflects the corrected values, including a recomputed implied rate, in the displayed history

#### Scenario: Delete an unallocated conversion
- **WHEN** the owner deletes a currency conversion and the backend accepts the deletion
- **THEN** the frontend removes it from the displayed history and updates the balance figures

#### Scenario: Edit or delete blocked on an allocated conversion
- **WHEN** the owner attempts to edit or delete a currency conversion that the backend rejects because it has funded an expense
- **THEN** the frontend shows the backend's explanatory error and leaves the conversion unchanged in the displayed history

#### Scenario: Conversion actions hidden from the funder
- **WHEN** the current user is the budget's matching funder, not its owner
- **THEN** the ledger history shows currency conversions without Edit or Delete actions

### Requirement: Reset ledger action
The frontend SHALL show a "Reset Ledger" action to the budget owner, requiring an explicit confirmation before submitting, that deletes all of the budget's funding receipts and currency conversions via the backend's reset endpoint.

#### Scenario: Reset with confirmation
- **WHEN** the owner triggers "Reset Ledger" and confirms the destructive-action dialog
- **THEN** the frontend sends the reset request and, on success, clears the displayed history and zeroes the balance figures

#### Scenario: Reset cancelled at the confirmation step
- **WHEN** the owner triggers "Reset Ledger" but dismisses the confirmation dialog without confirming
- **THEN** the frontend sends no request and the ledger remains unchanged

#### Scenario: Reset action hidden from the funder
- **WHEN** the current user is the budget's matching funder, not its owner
- **THEN** the ledger section does not show the "Reset Ledger" action
