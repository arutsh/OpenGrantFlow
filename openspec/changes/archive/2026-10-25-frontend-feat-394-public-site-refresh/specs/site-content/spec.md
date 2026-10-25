# Spec Delta

## ADDED Requirements

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
