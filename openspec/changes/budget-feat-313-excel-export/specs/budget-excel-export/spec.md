# Spec Delta

## Purpose

Lets a budget owner (or funder viewer) generate an Excel workbook of a single budget's plan, real-currency ledger, and expense history, for sharing outside the app — using either the built-in default format or an export template their organisation owns or their funder has shared with them.

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
The workbook's first sheet SHALL open with a header block (organisation name, donor name, project name, project period, estimated currency and rate), followed by a Budget Summary section (one row per category totalling that category's lines, plus a grand-total row), followed by a Detailed Budget section listing every budget line grouped under its category with a subtotal row per category, and a footer (a repeated total-expenditures row, an authorised-signatory line, and a project-contact-person line). Every amount is shown in the budget's `local_currency`; the donor-currency estimate (`amount ÷ estimated_exchange_rate`) is a live Excel formula referencing the header's rate cell, computed when `estimated_exchange_rate` is set.

#### Scenario: Categories and subtotals shown
- **WHEN** the budget has lines across more than one category
- **THEN** Sheet 1's Budget Summary and Detailed Budget sections both group lines under their category, each with a subtotal per category and a grand total for the whole budget

#### Scenario: Category with no lines is still shown
- **WHEN** a budget category has zero budget lines
- **THEN** the category still appears in both the Budget Summary and Detailed Budget sections with a zero subtotal, rather than being silently omitted

#### Scenario: No donor-currency estimate available
- **WHEN** the budget has no `estimated_exchange_rate` set
- **THEN** Sheet 1 shows the local-currency amount only, leaving the donor-currency estimate column blank for that budget rather than showing a fabricated figure

#### Scenario: Donor-currency estimate recalculates with the rate
- **WHEN** the budget has an `estimated_exchange_rate` set
- **THEN** every figure above a raw line amount is a live formula (a line's estimate divides its local amount by the header's rate cell; a category's subtotal and subtotal-estimate are `SUM` formulas over its lines; Budget Summary's category rows reference that category's own subtotal cell; every TOTAL/Total-expenditures row sums those reference cells), so editing the rate cell or any line amount in the exported file recalculates every subtotal, total, and estimate

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

### Requirement: Available export templates for a budget
The system SHALL provide an endpoint listing the export templates a given viewer may use for a given budget: the system default, every template owned by the viewer's organisation, and every template owned by the budget's funder that is marked shared with grantees. Each entry SHALL identify whether it is the system default, the viewer's own, or a funder's.

#### Scenario: Grantee sees a funder's shared template
- **WHEN** a grantee owner requests the available templates for a budget funded by a donor that owns a template marked shared with grantees
- **THEN** the response includes the system default, the grantee's own templates, and that donor's shared template, each tagged with its source

#### Scenario: A donor's private template is not offered
- **WHEN** the budget's funder owns a template marked private
- **THEN** that template does not appear in the grantee's available templates

#### Scenario: An unrelated organisation's shared template is not offered
- **WHEN** an organisation that does not fund this budget owns a template marked shared with grantees
- **THEN** that template does not appear in the available templates for this budget

#### Scenario: Funding relationship is revoked
- **WHEN** the donor-grantee relationship that made a donor's template available is revoked
- **THEN** the very next request for available templates omits that template, without waiting for any cache to expire

### Requirement: Explicit template selection
The export endpoint SHALL accept an optional template identifier and SHALL NOT select a template implicitly when more than one is available. When no identifier is given and exactly one template is available, the system SHALL use it. When no identifier is given and more than one is available, the system SHALL reject the request and indicate that a template must be chosen. When an identifier is given that is not among the viewer's available templates for that budget, the system SHALL reject the request as forbidden.

#### Scenario: Only the default is available
- **WHEN** a viewer with no organisation templates and no funder-shared templates exports a budget without naming a template
- **THEN** the system generates the workbook using the system default

#### Scenario: Choice required
- **WHEN** a viewer with more than one available template exports a budget without naming one
- **THEN** the request is rejected with an error stating that a template must be chosen, and no workbook is generated

#### Scenario: Template the viewer may not use
- **WHEN** a viewer names a template that is private to another organisation, or shared by an organisation that does not fund this budget
- **THEN** the request is rejected as forbidden

#### Scenario: Previously chosen template is no longer available
- **WHEN** a client re-sends a template identifier that has since been deleted or un-shared
- **THEN** the request is rejected with an error identifying that the template is no longer available, rather than falling back to another template

### Requirement: Template-scoped ownership
An export template SHALL belong to exactly one organisation and SHALL carry a visibility of either private or shared with grantees. Template names SHALL be unique within an owning organisation. Every query for templates SHALL be scoped to a requesting organisation; the system SHALL NOT expose a way to read templates without an organisational scope.

#### Scenario: Duplicate name within an organisation
- **WHEN** an organisation creates a second template with the name of one it already owns
- **THEN** the request is rejected, so which template a name refers to is never ambiguous

#### Scenario: Same name across organisations
- **WHEN** two different organisations each create a template named "Annual Report"
- **THEN** both are accepted, and each organisation only ever sees its own

### Requirement: Renderer options applied to the generated workbook
A template SHALL define its output as a bounded set of options over the built-in renderer — which sheets to include, whether the donor-currency estimate column is shown, column header label overrides, and whether the audit footer is shown — validated on write. The system SHALL reject an unrecognised option at write time rather than ignoring it at generation time. Options absent from a stored template SHALL fall back to the system default's value at generation time.

#### Scenario: Sheet subset
- **WHEN** a budget is exported with a template that includes only Sheet 1
- **THEN** the generated workbook contains only the Original Budget sheet

#### Scenario: Column labels overridden
- **WHEN** a template overrides the description column's header label
- **THEN** the generated workbook shows the overridden label, and every figure and formula is otherwise unchanged from the default output

#### Scenario: Unknown option rejected
- **WHEN** a template is saved with an option key the schema does not define
- **THEN** the save is rejected with a validation error

#### Scenario: Template predating a newly added option
- **WHEN** a template stored before an option existed is used for an export
- **THEN** the export succeeds, applying the system default's value for the missing option

### Requirement: System default template
The system SHALL provide a built-in default template, available to every organisation, that produces the same workbook this capability's other requirements describe. It SHALL be generated through the same rendering path as any other template, and SHALL NOT be editable or deletable by any organisation.

#### Scenario: Default reproduces the built-in format
- **WHEN** a budget is exported with the system default template
- **THEN** the workbook is identical to what the export produces with no template concept at all

#### Scenario: Default cannot be modified
- **WHEN** an organisation attempts to edit or delete the system default template
- **THEN** the request is rejected

### Requirement: Generated workbook records its template
The generated workbook SHALL identify, in its audit footer alongside the exporting user and timestamp, the name and version of the template that produced it. Editing a template SHALL advance its version, so a previously exported file remains attributable to the template content that produced it.

#### Scenario: Footer names the template
- **WHEN** a budget is exported with any template
- **THEN** the workbook's audit footer shows that template's name and version together with the exporting user and export timestamp

#### Scenario: Template edited after an export
- **WHEN** a template is edited after a workbook was exported with it
- **THEN** the template's version advances, and the already-exported workbook still shows the earlier version
