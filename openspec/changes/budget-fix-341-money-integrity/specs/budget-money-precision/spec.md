# Spec Delta

## Purpose

Guarantees that money amounts and exchange rates in the budget service are stored and computed exactly, with no binary floating-point drift, while keeping the JSON API contract unchanged for existing clients.

## ADDED Requirements

### Requirement: Money amounts are stored and computed exactly
The system SHALL store every money amount in the budget service as an exact decimal with 4 decimal places: budget totals, donor commitments, budget-line amounts, report-line amounts, funding receipts, currency-conversion amounts, and allocation amounts. Sums and differences of stored amounts computed by the server SHALL be exact.

#### Scenario: Sum of fractional amounts has no drift
- **WHEN** a budget has two lines with amounts `0.1` and `0.2`
- **THEN** the budget's `total_amount` is exactly `0.3`, not `0.30000000000000004`

#### Scenario: Large amount round-trips exactly
- **WHEN** a budget line is saved with amount `1234567.89`
- **THEN** reading it back returns exactly `1234567.89`

### Requirement: Exchange rates are stored at higher precision than amounts
The system SHALL store a budget's `estimated_exchange_rate` as an exact decimal with 10 decimal places, so small rates keep their significant digits.

#### Scenario: Small rate keeps its significant digits
- **WHEN** a budget owner sets `estimated_exchange_rate = 0.0073125` (e.g. EUR per KES)
- **THEN** reading it back returns exactly `0.0073125`

### Requirement: Excess input precision is rounded, not rejected
The system SHALL accept money and rate inputs with more decimal places than stored, rounding half-up to 4 decimal places for amounts and 10 for rates, rather than rejecting the request.

#### Scenario: Amount with too many decimal places
- **WHEN** a client submits a budget-line amount of `10.123456`
- **THEN** the line is saved with amount `10.1235`

#### Scenario: Float-derived rate from Excel import
- **WHEN** a budget is created via Excel import with a derived `estimated_exchange_rate` of `412.34567890123456`
- **THEN** the budget is created with `estimated_exchange_rate = 412.3456789012`

### Requirement: Money values remain JSON numbers on the wire
The system SHALL continue to serialise every money amount and rate in API responses as a JSON number, never as a string, so existing clients need no change. The system SHALL continue to accept JSON numbers for these fields on input.

#### Scenario: Response carries numbers
- **WHEN** a client fetches a budget with `total_amount` of `1500.5`
- **THEN** the response body contains `"total_amount": 1500.5` as a JSON number

### Requirement: Existing amounts are preserved through the precision migration
The system SHALL convert existing stored amounts and rates to the exact representation by rounding to their stored precision, and SHALL recompute every budget's `total_amount` from its converted lines, so no budget's total disagrees with its lines afterwards.

#### Scenario: Float artefact in existing data
- **WHEN** an existing budget line stored as `0.30000000000000004` is migrated
- **THEN** it becomes exactly `0.3000`, and its budget's `total_amount` equals the exact sum of its lines
