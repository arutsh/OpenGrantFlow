## MODIFIED Requirements

### Requirement: Reverting a confirmed budget to draft
The frontend SHALL let the budget owner revert a `confirmed` budget back to `draft` ("Cancel Confirmation"). The backend SHALL reject this transition if the budget has any report in a non-draft state (`submitted`, `approved`, `rejected`), or if the budget has any recorded funding receipt or currency conversion, and SHALL delete any draft-state report(s) belonging to the budget as part of a successful transition.

#### Scenario: Revert action visible to the owner only
- **WHEN** the current user owns a `confirmed` budget
- **THEN** the single-budget view shows a "Cancel Confirmation" action; a matching funder who is not the owner does not see this action

#### Scenario: Revert blocked by a non-draft report
- **WHEN** the owner triggers "Cancel Confirmation" on a budget that has a `submitted`, `approved`, or `rejected` report
- **THEN** the backend rejects the transition and the frontend shows an explanatory error, leaving the budget `confirmed`

#### Scenario: Revert blocked by existing ledger movement
- **WHEN** the owner triggers "Cancel Confirmation" on a budget that has any recorded funding receipt or currency conversion
- **THEN** the backend rejects the transition, the frontend shows an explanatory error directing the owner to the currency ledger section to resolve it (edit, delete, or reset the ledger), and the budget remains `confirmed`

#### Scenario: Revert succeeds and clears draft reports
- **WHEN** the owner triggers "Cancel Confirmation" on a budget whose reports (if any) are all `draft`, and the budget has no recorded funding receipts or currency conversions
- **THEN** the backend transitions the budget to `draft`, deletes its draft report(s), and the frontend reflects the budget as `draft` with no `start_date`
