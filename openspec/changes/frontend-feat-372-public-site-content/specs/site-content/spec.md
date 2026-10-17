# Spec Delta

## Purpose

Defines how public-site copy is authored: as versioned, individually addressable section files. The rendered pages and downstream consumers such as the site assistant's retrieval index read the same content through one contract.

## ADDED Requirements

### Requirement: Public-site copy is stored as one content file per section
All copy on the public pages (Home, How it works, Security & data, About, Contact, Legal) SHALL be stored in repository content files, one file per page section. It SHALL NOT be embedded in page component source. Each file SHALL consist of YAML frontmatter followed by an optional markdown body.

#### Scenario: Copy edit without code change
- **WHEN** an author changes the wording of a public-page section
- **THEN** the change is confined to that section's content file
- **AND** no page component source file is modified

#### Scenario: Section without prose body
- **WHEN** a section consists only of structured items (for example a list of cards)
- **THEN** its content file MAY have an empty markdown body and carry the items in frontmatter

### Requirement: Section frontmatter carries provenance metadata
Every section file's frontmatter SHALL include:
- `id`: a globally unique, stable identifier in the form `<page>.<slug>`
- `page`: one of `home`, `how-it-works`, `security`, `about`, `contact`, `legal`
- `anchor`: a URL fragment, unique within its page
- `title`: the section heading as shown to visitors
- `status`: `published` or `draft`

It MAY include `personas`, a subset of `grantee`, `funder` and `technical`, and `items`, a list of structured entries. Each item SHALL have a `title` or `quote` and a `body` or `attribution`. Each section's canonical URL SHALL be derivable as `<page route>#<anchor>`.

#### Scenario: Canonical URL derivation
- **WHEN** a section has `page: how-it-works` and `anchor: five-steps`
- **THEN** its canonical URL is `/how-it-works#five-steps`
- **AND** visiting that URL scrolls to the rendered section

#### Scenario: Missing required field
- **WHEN** a section file omits `id`, `page`, `anchor`, `title` or `status`
- **THEN** content validation fails and names the file and the missing field

### Requirement: Section IDs and anchors are stable
A section's `id` and `anchor` SHALL NOT change when only its copy changes. Renaming or removing an `id` or `anchor` SHALL be treated as a breaking content change, because downstream consumers cite sections by ID and URL.

#### Scenario: Duplicate identifier
- **WHEN** two section files declare the same `id`, or the same `anchor` on the same page
- **THEN** content validation fails and names both files

### Requirement: Draft content never reaches production
Sections with `status: draft` SHALL NOT be rendered in a production build. In non-production builds they SHALL render with a visible "TBC" marker that distinguishes them from published copy. Consumers other than the page renderer SHALL be able to exclude draft sections using the same field.

#### Scenario: Unconfirmed claim in production
- **WHEN** a section containing unconfirmed wording is marked `status: draft`
- **AND** the site is built for production
- **THEN** that section does not appear anywhere on the rendered page

#### Scenario: Reviewing drafts locally
- **WHEN** the site runs as a development or preview build
- **THEN** draft sections appear with a visible "TBC" marker

### Requirement: Content is validated in CI
Content validation SHALL run in the frontend CI workflow and fail the build on any contract violation, including a section ID that a page references but that does not exist.

#### Scenario: Page references a deleted section
- **WHEN** a page renders section `about.mission` and no file declares that ID
- **THEN** the frontend CI job fails

### Requirement: Section bodies render without raw HTML
Markdown section bodies SHALL be rendered with raw HTML disabled. HTML in a content file SHALL be displayed as text or dropped, never injected into the page.

#### Scenario: HTML in content body
- **WHEN** a section body contains `<script>` or other raw HTML
- **THEN** the rendered page contains no corresponding HTML element
