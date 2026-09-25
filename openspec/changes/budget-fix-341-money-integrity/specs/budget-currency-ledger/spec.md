# Spec Delta

## ADDED Requirements

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
