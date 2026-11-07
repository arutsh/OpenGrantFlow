## ADDED Requirements

### Requirement: Funding receipt correction
The system SHALL allow the budget owner to update or delete a previously recorded funding receipt, since nothing else references it.

#### Scenario: Update a funding receipt's amount or date
- **WHEN** the budget owner submits a corrected amount and/or received date for an existing funding receipt
- **THEN** the system updates that `FundingReceipt` record in place

#### Scenario: Delete a funding receipt
- **WHEN** the budget owner deletes an existing funding receipt
- **THEN** the system removes that `FundingReceipt` record and it no longer contributes to the budget's donor-currency balance

### Requirement: Currency conversion correction, guarded by allocation state
The system SHALL allow the budget owner to update or delete a previously recorded currency conversion only when it has zero report-line allocations against it, and SHALL reject the attempt otherwise, since an allocated conversion is already relied upon by the FIFO allocation trail.

#### Scenario: Update an unallocated conversion
- **WHEN** the budget owner submits corrected donor/local amounts or a corrected converted date for a currency conversion that has no allocation records
- **THEN** the system updates that `CurrencyConversion` record in place

#### Scenario: Delete an unallocated conversion
- **WHEN** the budget owner deletes a currency conversion that has no allocation records
- **THEN** the system removes that `CurrencyConversion` record and it no longer contributes to the budget's unconsumed balance

#### Scenario: Update or delete rejected once a conversion has funded an expense
- **WHEN** the budget owner attempts to update or delete a currency conversion that has one or more allocation records against it (directly consumed by a report line, or used to backfill a prior unsatisfied expense)
- **THEN** the system rejects the request, directing the owner to resolve the underlying report-line allocations first or reset the ledger

### Requirement: Ledger reset
The system SHALL allow the budget owner to delete all of a budget's funding receipts and currency conversions (and any allocation records referencing those conversions) in a single operation, regardless of allocation state.

#### Scenario: Reset a budget's ledger
- **WHEN** the budget owner triggers a ledger reset for a budget that has recorded funding receipts and/or currency conversions
- **THEN** the system deletes all of that budget's funding receipts, currency conversions, and any report-line allocation records referencing those conversions, leaving the budget's ledger balance at zero

#### Scenario: Reset on an already-empty ledger
- **WHEN** the budget owner triggers a ledger reset for a budget with no recorded funding receipts or currency conversions
- **THEN** the system completes the operation without error, leaving the ledger unchanged
