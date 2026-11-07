# donor-dashboard Specification

## Purpose
TBD - created by archiving change donor-dashboard. Update Purpose after archive.
## Requirements
### Requirement: Donor Budget Summary
The system SHALL provide an endpoint that returns, for the authenticated donor customer, the total count of budgets they fund and the sum of `total_amount` across those budgets.

#### Scenario: Donor with funded budgets requests summary
- **WHEN** an authenticated user whose customer has `is_donor = true` requests `GET /budgets/funded/summary`
- **THEN** the system SHALL return `total_budgets` equal to the count of budgets where `funding_customer_id` matches the donor's customer id, and `total_allocated` equal to the sum of `total_amount` across those same budgets

#### Scenario: Donor with no funded budgets requests summary
- **WHEN** an authenticated donor with zero budgets where they are the `funding_customer_id` requests `GET /budgets/funded/summary`
- **THEN** the system SHALL return `total_budgets: 0` and `total_allocated: 0`

#### Scenario: Non-donor requests summary
- **WHEN** an authenticated user whose customer has `is_donor = false` requests `GET /budgets/funded/summary`
- **THEN** the system SHALL respond with 403 Forbidden

### Requirement: Donor Grantee Directory
The system SHALL provide an endpoint that lists the distinct grantee customers funded by the authenticated donor, each enriched with the grantee's name and country, its count of funded budgets, and its total allocated amount.

#### Scenario: Donor requests grantee directory
- **WHEN** an authenticated donor requests `GET /budgets/funded/grantees`
- **THEN** the system SHALL return one entry per distinct `owner_id` among budgets where `funding_customer_id` matches the donor, each entry including the grantee's `name`, `country`, `budgets_count`, and `total_allocated`

#### Scenario: Same grantee funded via multiple budgets
- **WHEN** a donor funds three budgets owned by the same grantee customer
- **THEN** the grantee directory SHALL contain exactly one entry for that grantee, with `budgets_count` equal to 3 and `total_allocated` equal to the sum of `total_amount` across those three budgets

#### Scenario: Non-donor requests grantee directory
- **WHEN** an authenticated user whose customer has `is_donor = false` requests `GET /budgets/funded/grantees`
- **THEN** the system SHALL respond with 403 Forbidden

### Requirement: Donor Funded Budgets List
The system SHALL provide an endpoint that lists budgets where the authenticated donor is the `funding_customer_id`, each enriched with the owning grantee's name.

#### Scenario: Donor requests their funded budgets
- **WHEN** an authenticated donor requests `GET /budgets/funded/`
- **THEN** the system SHALL return every budget where `funding_customer_id` matches the donor's customer id, each including the budget's `name`, `status`, `total_amount`, and the owning grantee's name via `owner`

#### Scenario: Budget owned by a grantee but funded by a different donor is excluded
- **WHEN** a donor requests `GET /budgets/funded/` and a budget exists with a different `funding_customer_id`
- **THEN** that budget SHALL NOT appear in the response

#### Scenario: Non-donor requests funded budgets list
- **WHEN** an authenticated user whose customer has `is_donor = false` requests `GET /budgets/funded/`
- **THEN** the system SHALL respond with 403 Forbidden

### Requirement: Budget Total Amount Tracking
Each `Budget` SHALL expose a `total_amount` field equal to the sum of its budget lines' `amount`, derived from the lines whenever the budget is read rather than stored separately, so it can never disagree with them. `total_amount` SHALL be server-derived only: a budget create or update request that supplies it SHALL be rejected with a 422 response.

#### Scenario: Budget line added
- **WHEN** a new budget line with `amount = 500` is added to a budget whose current `total_amount` is 1000
- **THEN** the budget's `total_amount` SHALL become 1500

#### Scenario: Budget line amount updated
- **WHEN** a budget line's `amount` is changed from 500 to 300 on a budget whose current `total_amount` is 1500
- **THEN** the budget's `total_amount` SHALL become 1300

#### Scenario: Budget line deleted
- **WHEN** a budget line with `amount = 300` is deleted from a budget whose current `total_amount` is 1300
- **THEN** the budget's `total_amount` SHALL become 1000

#### Scenario: Budget with no lines
- **WHEN** a budget has no budget lines
- **THEN** its `total_amount` is `0`

#### Scenario: Client-supplied total rejected
- **WHEN** a client creates or updates a budget with a `total_amount` field in the request body
- **THEN** the system responds 422 stating `total_amount` is derived from budget lines, and no change is written

### Requirement: Donor Dashboard Page
The system SHALL provide a donor dashboard page displaying the donor's total budgets, total allocated amount, grantee directory, and funded-budgets list, with a "View Reports" action per budget that is disabled and mocked pending the separate report-review feature. At viewport widths below `sm` (640px), the grantee directory SHALL render as a horizontally scrolling row of cards and the funded-budgets list SHALL render as a vertical list of compact rows (name, grantee, amount, status) instead of the table used at `sm` and above.

#### Scenario: Donor views their dashboard
- **WHEN** an authenticated donor navigates to the donor dashboard page
- **THEN** the page SHALL display stat tiles for total budgets and total allocated, a list of grantees, and a table of funded budgets

#### Scenario: Donor views their dashboard on a narrow viewport
- **WHEN** an authenticated donor navigates to the donor dashboard page at a viewport width below 640px
- **THEN** the page SHALL display stat tiles for total budgets and total allocated, grantees as a horizontally scrolling row of cards, and funded budgets as a vertical list of compact rows rather than a table

#### Scenario: View Reports is not yet functional
- **WHEN** the donor dashboard renders a funded budget row
- **THEN** its "View Reports" button SHALL be rendered disabled and SHALL display a tooltip indicating the feature is coming soon, and SHALL NOT display fabricated report data

#### Scenario: Donor with no funded budgets views the dashboard
- **WHEN** an authenticated donor with `is_donor = true` but zero funded budgets views the page
- **THEN** the page SHALL show an empty/no-data state instead of an error or blank screen

### Requirement: Donor Dashboard Visibility Driven By Customer Flags
The system SHALL expose the authenticated customer's `is_ngo` and `is_donor` flags to the frontend (as JWT claims on the login/refresh access token, decoded client-side — not as separate fields in the response body), and the donor dashboard's navigation entry SHALL be shown or hidden based on `is_donor` alone — independent of `is_ngo`, since a customer may hold both flags at once.

#### Scenario: Donor-only customer
- **WHEN** the authenticated customer has `is_donor = true` and `is_ngo = false`
- **THEN** the frontend SHALL show the donor dashboard nav entry

#### Scenario: Grantee-only customer
- **WHEN** the authenticated customer has `is_donor = false` and `is_ngo = true`
- **THEN** the frontend SHALL NOT show the donor dashboard nav entry

#### Scenario: Customer that is both grantee and donor
- **WHEN** the authenticated customer has both `is_ngo = true` and `is_donor = true`
- **THEN** the frontend SHALL show both the existing owner-scoped dashboard navigation and the donor dashboard nav entry

#### Scenario: Direct navigation bypassing the nav entry
- **WHEN** a customer with `is_donor = false` navigates directly to the donor dashboard URL
- **THEN** the backend's `/budgets/funded/*` endpoints SHALL still respond with 403 Forbidden, regardless of client-side nav state

