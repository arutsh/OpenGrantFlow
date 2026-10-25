# site-content Specification

## Purpose
Defines how public-site copy is authored: as versioned, individually addressable section files. The rendered pages and downstream consumers such as the site assistant's retrieval index read the same content through one contract.
## Requirements
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

### Requirement: Assistant suggested questions are content, not indexed copy
The site assistant's suggested questions SHALL be stored in a repository content file, not in component source, as a default set plus one set each for `grantee`, `funder` and `technical`. The file SHALL be stored outside the public-site section directory so the retrieval index does not ingest it. Content validation SHALL fail if any set is missing or empty, or holds more than four questions.

#### Scenario: Editing a suggested question
- **WHEN** an author rewords a suggested question
- **THEN** the change is confined to the suggested-questions content file

#### Scenario: Questions are not retrieved as sources
- **WHEN** the retrieval index is rebuilt
- **THEN** no indexed chunk comes from the suggested-questions file

#### Scenario: Invalid set
- **WHEN** the `funder` set is missing or holds five questions
- **THEN** content validation fails and names the file and the set

### Requirement: Sections can opt out of the retrieval index
A site-content section SHALL be able to declare `indexed: false` in its frontmatter. Such a section SHALL still render on its page but SHALL NOT be ingested into the retrieval index. Content validation SHALL fail if `indexed` is present and not a boolean. Each page's call-to-action band SHALL be marked `indexed: false`.

#### Scenario: CTA band is not cited
- **WHEN** the retrieval index is rebuilt
- **THEN** no indexed chunk comes from a `<page>.cta` section

#### Scenario: Opting out after publication
- **WHEN** an already-indexed section gains `indexed: false`
- **THEN** its chunk is removed from the index on the next ingestion

#### Scenario: Invalid flag
- **WHEN** a section sets `indexed: "false"` as a string
- **THEN** content validation fails and names the file and the field

### Requirement: Privacy notice banner text is content
The privacy notice banner's text SHALL be stored in a repository content file outside the public-site section directory, with frontmatter carrying `status` (`published` or `draft`) and a `version` string. Content validation SHALL fail if either field is missing or the body is empty.

#### Scenario: Publishing the notice
- **WHEN** an author changes the notice's `status` from `draft` to `published`
- **THEN** the banner appears in production builds with no component change

#### Scenario: Missing version
- **WHEN** the notice file omits `version`
- **THEN** content validation fails and names the file and the field
