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

### Requirement: Privacy notice banner text is content
The privacy notice banner's text SHALL be stored in a repository content file outside the public-site section directory, with frontmatter carrying `status` (`published` or `draft`) and a `version` string. Content validation SHALL fail if either field is missing or the body is empty.

#### Scenario: Publishing the notice
- **WHEN** an author changes the notice's `status` from `draft` to `published`
- **THEN** the banner appears in production builds with no component change

#### Scenario: Missing version
- **WHEN** the notice file omits `version`
- **THEN** content validation fails and names the file and the field
