# Spec Delta

## MODIFIED Requirements

### Requirement: Budget Total Amount Tracking
Each `Budget` SHALL carry a `total_amount` field equal to the sum of its budget lines' `amount`, kept up to date whenever a budget line belonging to it is created, updated, or deleted. The line change and the updated `total_amount` SHALL be persisted together or not at all, so a failed write never leaves a stale total. `total_amount` SHALL be server-derived only: a budget create or update request that supplies it SHALL be rejected with a 422 response.

#### Scenario: Budget line added
- **WHEN** a new budget line with `amount = 500` is added to a budget whose current `total_amount` is 1000
- **THEN** the budget's `total_amount` SHALL become 1500

#### Scenario: Budget line amount updated
- **WHEN** a budget line's `amount` is changed from 500 to 300 on a budget whose current `total_amount` is 1500
- **THEN** the budget's `total_amount` SHALL become 1300

#### Scenario: Budget line deleted
- **WHEN** a budget line with `amount = 300` is deleted from a budget whose current `total_amount` is 1300
- **THEN** the budget's `total_amount` SHALL become 1000

#### Scenario: Failed recalculation rolls back the line change
- **WHEN** a budget line is added but persisting the recalculated `total_amount` fails
- **THEN** neither the new line nor a changed total is persisted, and the budget's lines and `total_amount` remain consistent

#### Scenario: Client-supplied total rejected
- **WHEN** a client creates or updates a budget with a `total_amount` field in the request body
- **THEN** the system responds 422 stating `total_amount` is derived from budget lines, and no change is written
