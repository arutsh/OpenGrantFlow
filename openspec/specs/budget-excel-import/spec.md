# budget-excel-import Specification

## Purpose
Uploading an org's Excel budget file and getting back a populated `ai_draft` budget with lines, via AI-first extraction that's shared and reused across organizations once a donor's template layout is recognized.

## Requirements

### Requirement: Excel upload produces a draft budget
The chat service SHALL expose `POST /chat/import-excel` accepting a single `.xlsx` file upload, orchestrate extraction across the budget and AI services, and create a budget in `ai_draft` status via a `create_budget_with_lines` tool call against budget service's budget-with-lines creation path, without requiring the user to map columns before upload. The budget service SHALL expose `POST /budgets/excel/prepare-import`, accepting the same upload, to clean the sheet and attempt a template fingerprint match on chat service's behalf.

#### Scenario: Successful import creates an ai_draft budget
- **WHEN** an authenticated user uploads a `.xlsx` file with at least one identifiable budget line
- **THEN** chat service creates a budget with `status: ai_draft` and returns its id, with lines populated from the extracted data

#### Scenario: File is not a valid Excel workbook
- **WHEN** the uploaded file cannot be parsed as an `.xlsx` workbook
- **THEN** budget service's `prepare-import` step rejects the request with an error and chat service creates no budget

### Requirement: AI-based line extraction is BYOK-preferred with a platform-funded fallback
The AI service SHALL extract category, description, amount, and currency per budget line from a cleaned representation of the sheet — provided by chat service, sourced from budget service's `prepare-import` step — using a structured-output AI call. The AI service SHALL use the organization's configured AI provider key when one exists, and SHALL fall back to a GrantFlow-funded low-cost model when no key is configured, so extraction quality does not depend on the organization having set up AI. This behavior is unchanged by which service calls it — only the caller (chat service, not budget service) changed.

#### Scenario: Organization with a configured provider key
- **WHEN** an organization with a configured AI provider key uploads a file requiring AI extraction (no matching template fingerprint)
- **THEN** the AI service performs the extraction using that organization's provider key

#### Scenario: Organization with no configured provider key
- **WHEN** an organization with no AI provider key configured uploads a file requiring AI extraction
- **THEN** the AI service performs the extraction using a GrantFlow-funded low-cost model rather than skipping AI or blocking the import

### Requirement: AI extraction calls are audit-logged and rate-limited
The AI service SHALL record an audit log entry for every AI extraction call, including which funding source was used (organization's own key or GrantFlow-funded), token counts, and cost. The AI service SHALL apply a per-organization rate limit to GrantFlow-funded extraction calls.

#### Scenario: Audit log records funding source
- **WHEN** an AI extraction call completes, successfully or not
- **THEN** an audit log entry is written recording whether it was BYOK or GrantFlow-funded, along with token usage and cost

#### Scenario: Platform-funded rate limit exceeded
- **WHEN** an organization with no provider key configured exceeds its rate limit for GrantFlow-funded extraction calls
- **THEN** the AI service rejects the request with an explanatory error, and chat service surfaces this as a failed import rather than performing the call

### Requirement: Unresolved or low-confidence data is preserved, never dropped
When the AI extraction cannot confidently resolve part of a row to a canonical budget field, the service SHALL still include it in the created budget by placing the raw source data into the corresponding budget line's `extra_fields`, rather than omitting it from the import.

#### Scenario: Low-confidence line still produces line data
- **WHEN** a row's extraction confidence is below the threshold for a clean match
- **THEN** the resulting budget line is still created, with the raw row data included in `extra_fields`

### Requirement: A cleanly resolved line never carries redundant currency data in extra_fields
When a line's extraction confidence meets the platform's threshold, chat service SHALL discard any `extra_fields` the AI service returned for it — regardless of content — rather than persisting it, since a resolved line's donor-currency equivalent is already derivable from `amount`, `local_currency`, `target_currency`, and `estimated_exchange_rate` without duplication.

#### Scenario: High-confidence line drops model-supplied extra data
- **WHEN** a line's extraction confidence meets the threshold, even if the AI service returned a non-null `extra_fields` for it (e.g. a donor-currency value read alongside the local-currency amount)
- **THEN** the created budget line's `extra_fields` is null

### Requirement: Total and summary rows are excluded from line extraction
Budget service's `prepare-import` step SHALL exclude rows that represent category totals or a grand total from becoming individual budget lines.

#### Scenario: Grand total row excluded
- **WHEN** a sheet contains a row whose first cell reads "Total Project" (or an equivalent total-row pattern)
- **THEN** that row does not appear as a budget line in the created budget

### Requirement: Donor templates are shared, named, and reused by structural fingerprint
Budget service SHALL persist a recognized template layout as a named, donor-scoped `DonorTemplateModel` record keyed by a fingerprint of the sheet's normalized structure. Fingerprint lookup SHALL be global across organizations: any organization uploading a file matching an existing template's fingerprint SHALL reuse its stored structure and skip AI extraction, regardless of which organization created that template record.

#### Scenario: First recognized upload can be saved as a template
- **WHEN** an organization completes an AI-extracted import and confirms the resulting budget without editing its lines
- **THEN** chat service offers an optional prompt to save the extraction's structure as a named, reusable `DonorTemplateModel`

#### Scenario: A different organization reuses an existing template
- **WHEN** an organization uploads a file whose structure fingerprint matches an existing `DonorTemplateModel`, regardless of which organization created that template
- **THEN** budget service's `prepare-import` step returns lines extracted directly from the stored structure, and chat service does not call the AI extraction endpoint

#### Scenario: Changed layout does not match a stored template
- **WHEN** an uploaded file's structure fingerprint does not match any stored `DonorTemplateModel`
- **THEN** budget service's `prepare-import` step reports no match, and chat service performs AI extraction rather than reusing an unrelated stored structure

### Requirement: A budget created via Excel import records its source template
When chat service calls `create_budget_with_lines` to create a budget from an Excel import, it SHALL pass the matched or newly created `DonorTemplateModel`'s id as `donor_template_id`, and budget service SHALL set the created budget's existing `donor_template_id` field from it, when one exists.

#### Scenario: Provenance recorded on template match
- **WHEN** an import matches an existing `DonorTemplateModel` by fingerprint
- **THEN** the created budget's `donor_template_id` references that template

#### Scenario: No provenance when no template is saved
- **WHEN** an import uses AI extraction and the user does not save the result as a template
- **THEN** the created budget's `donor_template_id` remains unset

### Requirement: AI extraction resolves local currency, donor currency, donor total, and grant duration
The AI service SHALL report, in addition to per-line data, the sheet's local currency (the currency budget line amounts are expressed in) with a confidence score, the donor/target currency (the currency the donor commits funding in, when the sheet distinguishes the two), the donor's stated total commitment in that target currency as read directly from the sheet's own total row, and the grant's stated duration in months when present. Per-line `amount` SHALL be drawn from the local-currency column when a sheet has separate local- and target-currency columns.

#### Scenario: Sheet with separate local and donor-currency columns
- **WHEN** an uploaded sheet has one amount column in the org's local currency and a second in the donor's currency (e.g. "Costs in local currency" / "Costs in Euro")
- **THEN** each extracted line's amount reflects the local-currency column, and the AI service reports the target/donor currency and the sheet's own grand total in that currency separately

#### Scenario: Local currency not explicitly labeled
- **WHEN** the sheet does not name the local currency's ISO code directly
- **THEN** the AI service infers it from other sheet context (e.g. the grantee organization's country) and reports a confidence score for that inference

#### Scenario: Local-currency column is formula-derived from the donor currency
- **WHEN** a sheet's local-currency amount column is itself computed by a formula referencing the donor-currency column (e.g. `=eur_col*rate`), rather than entered directly
- **THEN** budget service's `prepare-import` step resolves each such cell to its last-calculated value rather than blanking it, so the AI extraction call still receives real local-currency amounts to read `amount` from

#### Scenario: Model reports local and target amounts under the wrong column
- **WHEN** a sheet has both a local-currency and a donor-currency amount column, and the AI service's per-line `local_amount`/`target_amount` are collectively a closer match to `donor_total_amount` when swapped than as reported
- **THEN** chat service swaps `local_amount`/`target_amount` (and the persisted `excel_import_structure.amount_col`) before creating budget lines, rather than trusting the AI service's per-line labeling as-is

### Requirement: Missing or low-confidence local currency falls back to the organization's default
When the AI-reported local currency is null or its confidence is below the platform's low-confidence threshold, budget service SHALL use the organization's own configured default currency for the created budget instead of leaving it unset or trusting an unreliable value.

#### Scenario: Low-confidence currency falls back to org default
- **WHEN** a budget is created via Excel import and the extracted local currency is null, or its confidence is below the threshold
- **THEN** the created budget's `local_currency` is set from the organization's own default currency rather than the extracted value

### Requirement: Estimated exchange rate is computed deterministically, not extracted directly
When both a donor total amount (in target currency) and extracted local-currency line amounts are available, chat service SHALL compute `estimated_exchange_rate` as the ratio of the summed local-currency line amounts to the donor total amount, rather than asking the AI service to compute or report it directly.

#### Scenario: Exchange rate derived from totals
- **WHEN** a budget is created via Excel import with both local-currency line amounts and a donor total amount
- **THEN** the created budget's `estimated_exchange_rate` equals the sum of its lines' amounts divided by `donor_total_amount`

### Requirement: Uploaded files are stored through existing cloud-agnostic storage
Budget service's `prepare-import` step SHALL persist the uploaded Excel file using the existing cloud-agnostic storage capability rather than local disk.

#### Scenario: Uploaded file is retrievable via configured storage backend
- **WHEN** a file is uploaded for import
- **THEN** budget service stores it through the cloud-agnostic storage service and records a reference to it, not a local filesystem path

### Requirement: Prepare-import bounds workbook processing before parsing
Budget service's `prepare-import` step SHALL reject an upload before full parsing when any of these limits is exceeded: total uncompressed archive size, uncompressed size of any single archive member, compression ratio, number of archive members, worksheet row or column extent, or number of populated cells. The worksheet check SHALL be based on the cells actually present in the file, not on the declared used range, and SHALL NOT allocate memory in proportion to the used range. A rejected upload SHALL receive a 400 response naming the limit that was exceeded, and SHALL NOT be stored.

#### Scenario: Sparse workbook with a huge used range
- **WHEN** a user uploads a small `.xlsx` whose only cells are `A1` and `XFD1048576`
- **THEN** the service rejects it with 400 without iterating the used range, and memory use stays bounded

#### Scenario: Compression bomb
- **WHEN** a user uploads an `.xlsx` under the upload size cap whose worksheet XML decompresses beyond the uncompressed-size or ratio limit
- **THEN** the service rejects it with 400 before handing it to the spreadsheet parser

#### Scenario: Realistic donor template
- **WHEN** a user uploads a typical donor budget template (hundreds of rows, tens of columns)
- **THEN** it passes the limits and is processed as before

### Requirement: Workbook parsing does not block the service
Budget service SHALL parse uploaded workbooks outside the request event loop, with a bounded number of concurrent parses per process, so that one upload cannot stall unrelated requests.

#### Scenario: Concurrent request during a parse
- **WHEN** a large but within-limits workbook is being parsed
- **THEN** an unrelated budget API request on the same instance is served without waiting for the parse to finish

### Requirement: Archives with unexpected members are rejected
Budget service's `prepare-import` step SHALL reject an upload whose zip archive contains any member outside the expected `.xlsx` package parts (`[Content_Types].xml`, `_rels/`, `xl/`, `docProps/`, `customXml/`, `docMetadata/`, and their standard subpaths). A rejected upload SHALL receive a 400 response and SHALL NOT be stored.

#### Scenario: Polyglot file with a hidden extra member
- **WHEN** a user uploads a workbook that parses as a valid `.xlsx` but its zip archive also contains an unrelated file (e.g. `payload.exe`)
- **THEN** the service rejects it with 400 before storing it

#### Scenario: Realistic donor template
- **WHEN** a user uploads a typical donor `.xlsx` template produced by Excel or LibreOffice, including SharePoint/OneDrive metadata or a sensitivity label
- **THEN** its member list passes the check and it is processed as before
