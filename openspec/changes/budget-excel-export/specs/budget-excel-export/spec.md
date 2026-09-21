# Spec Delta

## Purpose

Lets a budget owner (or funder viewer) generate a 3-sheet Excel workbook of a single budget's plan, real-currency ledger, and expense history, for sharing outside the app.

## ADDED Requirements

### Requirement: Single-budget Excel export endpoint
The system SHALL provide an endpoint that generates and streams a `.xlsx` workbook for exactly one budget, computed on demand from current data (not persisted or cached), accessible to anyone permitted to view that budget (owner or funder, matching existing budget-read authorization).

#### Scenario: Owner exports a budget
- **WHEN** the budget's owner requests the export for a budget they own
- **THEN** the system returns a `.xlsx` file streamed in the response, reflecting the budget's current lines, ledger, and report data

#### Scenario: Funder views a funded budget's export
- **WHEN** a funder who funds the budget (`funding_customer_id`) requests its export
- **THEN** the system returns the same workbook a viewer with read access would see

#### Scenario: Unauthorized user is rejected
- **WHEN** a user who is neither the budget's owner nor its funder requests the export
- **THEN** the system rejects the request without generating a workbook

### Requirement: Sheet 1 — Original Budget
The workbook's first sheet SHALL list every budget line grouped by category, with a subtotal row per category and a grand-total row, each line showing its amount in the budget's `local_currency` and a derived estimate in the budget's `actual_currency` (`amount ÷ estimated_exchange_rate`) when `estimated_exchange_rate` is set.

#### Scenario: Categories and subtotals shown
- **WHEN** the budget has lines across more than one category
- **THEN** Sheet 1 groups lines under their category, with a subtotal per category and a grand total for the whole budget

#### Scenario: No donor-currency estimate available
- **WHEN** the budget has no `estimated_exchange_rate` set
- **THEN** Sheet 1 shows the local-currency amount only, leaving the donor-currency estimate column blank for that budget rather than showing a fabricated figure

### Requirement: Sheet 2 — Budget vs. Report Dashboard, income section
The workbook's second sheet SHALL open with an income section listing every recorded currency conversion for the budget as its own row (converted date, donor-currency amount, local-currency amount, implied rate), plus a total row, rather than one row per funding receipt.

#### Scenario: Multiple conversions from one receipt
- **WHEN** a budget has one funding receipt but several currency conversions recorded against it
- **THEN** the income section lists each conversion as a separate row with its own date and implied rate, not one blended row

### Requirement: Sheet 2 — Budget vs. Report Dashboard, expense columns
For each budget line (and category subtotal), Sheet 2 SHALL show: total expenses in `local_currency` (sum of that line's report-line amounts); total expenses converted to `actual_currency`, using the real per-allocation conversion rate for the portion covered by a `CurrencyConversion` and the budget's `estimated_exchange_rate` for any unsatisfied remainder; and a deviation column (budgeted amount converted to `actual_currency` via `estimated_exchange_rate`, minus the converted total expenses). The workbook SHALL visually distinguish a converted-expense figure that includes an estimated (not real-rate) portion from one derived entirely from real conversions.

#### Scenario: Expense fully covered by real conversions
- **WHEN** a budget line's report-line expenses are fully covered by allocated currency conversions
- **THEN** its converted-expense figure uses only real per-allocation rates, with no estimated-rate flag

#### Scenario: Expense partially unconverted
- **WHEN** a budget line has report-line expenses whose allocation to currency-conversion lots is incomplete
- **THEN** its converted-expense figure combines the real-rate portion with the `estimated_exchange_rate`-derived portion for the remainder, and is flagged as including an estimate

#### Scenario: No report-line expenses yet
- **WHEN** a budget line has no report-line expenses recorded
- **THEN** its expense and converted-expense figures show zero, and its deviation equals its full budgeted amount

### Requirement: Sheet 3 — List of Expenses with per-allocation sublines
The workbook's third sheet SHALL list every report-line expense across all of the budget's reports, one row per report line when its full amount is covered by a single currency-conversion lot, or one row per allocation (subline) when a report line's amount is funded by more than one lot — each subline row carrying that allocation's own conversion date, converted amount, and implied rate.

#### Scenario: Expense funded by a single lot
- **WHEN** a report-line expense is fully allocated to exactly one currency-conversion lot
- **THEN** Sheet 3 shows it as a single row with that lot's date and rate

#### Scenario: Expense funded by multiple lots
- **WHEN** a report-line expense straddles more than one currency-conversion lot (e.g., one receipt converted across four separate events)
- **THEN** Sheet 3 shows one row per allocation, each with its own conversion date and implied rate, and the rows' amounts sum to the expense's full amount

#### Scenario: Expense not yet allocated
- **WHEN** a report-line expense has no currency-conversion allocation at all
- **THEN** Sheet 3 shows it as a single row with its local-currency amount and no conversion date or rate
