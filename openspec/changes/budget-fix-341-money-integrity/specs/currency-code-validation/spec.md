# Spec Delta

## Purpose

Ensures every currency code stored on a budget is a real ISO 4217 code, and gives clients the same authoritative list the server validates against.

## ADDED Requirements

### Requirement: Budget writes reject invalid currency codes
The system SHALL validate `local_currency` and `actual_currency` against the ISO 4217 currency list on every budget write that accepts them: budget creation, budget update, and budget creation with lines (including creation via chat's Excel import). An unrecognised code SHALL be rejected with a 422 response naming the offending field, and no budget data SHALL be written.

#### Scenario: Invalid code on budget creation
- **WHEN** a client creates a budget with `local_currency = "XYZ"`
- **THEN** the system responds 422 identifying `local_currency` as not a valid ISO 4217 code, and no budget is created

#### Scenario: Invalid code on budget update
- **WHEN** a client updates an existing budget with `actual_currency = "EURO"`
- **THEN** the system responds 422 identifying `actual_currency`, and the budget is unchanged

#### Scenario: Invalid code on budget creation with lines
- **WHEN** a budget-with-lines creation request carries `actual_currency = "ABC"`
- **THEN** the system responds 422, and neither the budget nor any of its lines or categories is created

#### Scenario: Omitted currency is not validated
- **WHEN** a budget update omits `actual_currency`, or sends it as null
- **THEN** the system applies the update without currency validation errors

### Requirement: Currency codes are normalised to uppercase
The system SHALL accept a valid ISO 4217 code in any letter case and SHALL store it in uppercase.

#### Scenario: Lowercase code accepted
- **WHEN** a client creates a budget with `local_currency = "kes"`
- **THEN** the budget is created with `local_currency = "KES"`

### Requirement: Existing budgets remain readable regardless of stored currency code
The system SHALL NOT apply currency-code validation when returning budgets. A budget whose stored code predates validation and is not valid ISO 4217 SHALL still be returned normally by every read endpoint.

#### Scenario: Legacy invalid code on read
- **WHEN** a client fetches a budget whose stored `local_currency` is not a valid ISO 4217 code
- **THEN** the system returns the budget successfully with the stored code unchanged

### Requirement: Currency list endpoint
The system SHALL provide an authenticated endpoint that returns the full ISO 4217 currency list the server validates against, each entry with its code and name, sorted by code. Every code this endpoint returns SHALL pass budget-write validation, and every code budget-write validation accepts SHALL be in this list.

#### Scenario: Client fetches the currency list
- **WHEN** an authenticated user requests the currency list
- **THEN** the system returns every ISO 4217 currency as `{code, name}` entries sorted by code, including codes beyond the frontend's former 11-code subset (e.g. `AMD`, `JPY`)

#### Scenario: Unauthenticated request
- **WHEN** an unauthenticated client requests the currency list
- **THEN** the system responds 401

### Requirement: Currency picker offers the full ISO 4217 list
The frontend SHALL populate every budget currency picker from the currency list endpoint instead of a hardcoded subset.

#### Scenario: Picking a currency outside the old subset
- **WHEN** a budget owner opens a currency picker on the budget form
- **THEN** the picker offers every currency returned by the currency list endpoint, including ones not in the former hardcoded 11-code list
