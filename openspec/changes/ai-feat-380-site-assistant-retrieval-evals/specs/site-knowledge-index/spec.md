# Spec Delta

## Purpose

Keeps a queryable, provenance-tagged index of the site's own content (public pages and user-guide docs) in sync with its sources, so retrieval always answers from what's actually published.

## ADDED Requirements

### Requirement: Published site-content sections are indexed
The system SHALL index every `status: published` section file under `frontend-typescript/src/content/site/**` as one `site_chunks` row, carrying `content_id` (the section's `id`), `url` (`<page route>#<anchor>`), `page_title`, `heading`, `personas`, and the rendered text.

#### Scenario: Published section indexed
- **WHEN** ingestion runs and a section file has `status: published`
- **THEN** a `site_chunks` row exists with that section's `content_id`, `url`, and text

#### Scenario: Draft section excluded
- **WHEN** ingestion runs and a section file has `status: draft`
- **THEN** no `site_chunks` row is created or kept for that section's `content_id`

### Requirement: Guide docs are chunked by H2 and indexed
The system SHALL split each file under `docs/user-guide/*.md` into one chunk per top-level (H2) section, writing a `site_chunks` row per chunk with `content_id` in the form `<doc-slug>.<heading-slug>` and `url` in the form `/guides/<doc-slug>#<heading-slug>`.

#### Scenario: Guide doc split into chunks
- **WHEN** ingestion processes `docs/user-guide/ngo-guide.md` containing multiple `##` headings
- **THEN** one `site_chunks` row is created per `##` heading, each with a distinct `content_id` and `url`

### Requirement: Ingestion is idempotent and prunes stale chunks
The system SHALL upsert `site_chunks` rows keyed by `content_id`, rewriting a row only when its source text's hash (`content_version`) changes, and SHALL delete rows whose `content_id` no longer exists among published sources.

#### Scenario: Unchanged content is not rewritten
- **WHEN** ingestion runs twice in a row with no source changes
- **THEN** the second run's `content_version` values are unchanged from the first run

#### Scenario: Unpublished section is removed from the index
- **WHEN** a previously published section's `status` changes to `draft` or the section file is deleted
- **THEN** the next ingestion run deletes that section's `site_chunks` row

### Requirement: Ingestion runs on ai service startup
The system SHALL run ingestion once during FastAPI application startup, before the service accepts traffic.

#### Scenario: Startup triggers ingestion
- **WHEN** the ai service process starts
- **THEN** ingestion completes and `site_chunks` reflects the current published sources before the first request is served
