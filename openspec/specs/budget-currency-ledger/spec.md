# budget-currency-ledger Specification

## Purpose
TBD - created by archiving change budget-reports. Update Purpose after archive.
## Requirements
### Requirement: Funding receipt recording
The system SHALL allow recording a donor-currency payment landing against a budget, capturing the amount received and when.

#### Scenario: Record a funding receipt
- **WHEN** the budget owner records a funding receipt with an amount and a received date
- **THEN** the system creates a `FundingReceipt` record scoped to that budget, denominated in the budget's `actual_currency`

### Requirement: Currency conversion recording
The system SHALL allow recording a real bank foreign-exchange event that converts a donor-currency amount into a local-currency amount, deriving the exchange rate from the two recorded amounts rather than accepting a rate directly.

#### Scenario: Record a currency conversion
- **WHEN** the budget owner records a conversion with a donor-currency amount converted and the local-currency amount received
- **THEN** the system creates a `CurrencyConversion` record without accepting or storing a separately entered exchange rate

### Requirement: FIFO consumption of conversion lots by report-line expenses
The system SHALL allocate each report-line expense against the budget's unconsumed currency-conversion lots, oldest lot first, splitting the expense across more than one lot when it exceeds the remaining balance of the oldest lot, and SHALL run this allocation automatically when the report line is created.

#### Scenario: Expense fully covered by the oldest lot
- **WHEN** a report line is created with an amount fully covered by the oldest unconsumed conversion lot
- **THEN** the system creates one allocation record linking the report line to that lot for the full amount

#### Scenario: Expense straddles two lots
- **WHEN** a report line's amount exceeds the remaining balance of the oldest unconsumed lot but is covered once the next-oldest lot is included
- **THEN** the system creates allocation records against the oldest lot for its remaining balance and against the next-oldest lot for the rest

### Requirement: Overspend against unconverted balance is allowed
The system SHALL permit a report-line expense to exceed all currently unconsumed conversion lots without rejecting, warning on, or requiring approval for it. Any portion of the expense not covered by an existing lot SHALL be recorded as unsatisfied rather than linked to an allocation.

#### Scenario: Expense exceeds all available lots
- **WHEN** a report line's amount exceeds the sum of all unconsumed conversion lots for its budget
- **THEN** the system creates the report line and allocates whatever lot balance exists, leaving the remainder of the expense unsatisfied and the budget's ledger balance negative

### Requirement: New conversions retroactively satisfy outstanding expenses before funding new ones
The system SHALL, when a new currency conversion is recorded, allocate its balance first against the budget's outstanding unsatisfied report-line amounts — oldest expense first — before any remaining balance of that lot becomes available to a newly created report line. This lets an expense incurred before its funding was converted (e.g. weekend petty-cash spend converted the following business day) still be traced to the specific conversion that ultimately funded it.

#### Scenario: A later conversion pays down a prior overspend
- **WHEN** a currency conversion is recorded for a budget that has an outstanding unsatisfied report-line expense from an earlier overspend
- **THEN** the system creates an allocation record linking that earlier report line to the new conversion, for the smaller of the unsatisfied amount or the new lot's balance, before any of the new lot is made available to new expenses

#### Scenario: Multiple outstanding expenses satisfied oldest-first
- **WHEN** a new conversion is recorded for a budget with more than one outstanding unsatisfied report-line expense
- **THEN** the system satisfies the oldest outstanding expense first, moving to the next only after the oldest is fully allocated or the new lot's balance is exhausted

### Requirement: Every allocated report-line amount traces to a real conversion
The system SHALL ensure that once a report-line amount is fully allocated, its allocation records sum to its full amount and each references an actual `CurrencyConversion`, so the donor-currency equivalent of any expense is always reconstructible from real bank transactions — regardless of whether that allocation completed immediately or only after a later conversion satisfied it.

#### Scenario: Fully satisfied expense has a complete allocation trail
- **WHEN** a report-line expense has been fully allocated, whether immediately at creation or later once a subsequent conversion satisfied the remainder
- **THEN** the sum of its allocation records equals its full amount, and each allocation record references a specific conversion

### Requirement: Per-currency ledger balance reporting
The system SHALL report funding and conversion balances grouped by currency, never blending amounts across currencies into a single total.

#### Scenario: Balance shown per currency
- **WHEN** a budget's ledger balance is requested
- **THEN** the system reports the unconsumed donor-currency balance and the unconsumed local-currency balance separately, never combined into one figure

### Requirement: Ledger allocation is exact
The system SHALL perform FIFO allocation and ledger balance calculations with exact decimal arithmetic. A conversion lot SHALL be treated as fully consumed only when its remaining balance is exactly zero, and a report-line expense as fully allocated only when its allocations sum to exactly its amount, with no rounding tolerance.

#### Scenario: Fractional expense splits exactly across lots
- **WHEN** a report line of `100.10` is allocated across an oldest lot with `33.37` remaining and a next lot with ample balance
- **THEN** the allocations are exactly `33.37` and `66.73`, summing to exactly `100.10`, and the oldest lot's remaining balance is exactly `0`

#### Scenario: Tiny remainder is not ignored
- **WHEN** an expense exceeds all available lots by `0.0001`
- **THEN** that `0.0001` is recorded as unsatisfied rather than treated as fully allocated

#### Scenario: Ledger balance is exact
- **WHEN** a budget has funding receipts of `0.1` and `0.2` and no conversions
- **THEN** the reported donor-currency balance is exactly `0.3`
