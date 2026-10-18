# Spec Delta

## MODIFIED Requirements

### Requirement: Single-turn, non-streaming request and response
The `ask` endpoint SHALL accept `{question, persona?}`, where `persona` is one of `grantee`, `funder` or `technical`, and SHALL return one JSON body `{answer, answerable, citations[], answer_id}` after generation completes. Each citation SHALL be `{content_id, url, title}`. `answer_id` SHALL be the identifier of the stored question record, or `null` when writing the record failed. The system SHALL NOT accept or use earlier questions or answers as context.

#### Scenario: Answer returned as one JSON body
- **WHEN** a visitor asks an answerable question
- **THEN** the response is a single JSON body with `answerable: true`, a non-empty `answer`, and at least one citation

#### Scenario: Prior-turn fields are rejected
- **WHEN** a request body includes fields other than `question` and `persona`
- **THEN** the system returns 422

#### Scenario: Answer ID identifies the record
- **WHEN** a question is answered and its record is written
- **THEN** the response's `answer_id` identifies that record

### Requirement: Question length is limited
The system SHALL reject a question that is empty or longer than the configured maximum (500 characters by default) with 422 before retrieval or any model call. The limit SHALL apply to the question as submitted, before personal details are removed.

#### Scenario: Over-long question
- **WHEN** a visitor submits a 501-character question with the default limit
- **THEN** the system returns 422 and makes no model call

#### Scenario: Limit checked before redaction
- **WHEN** a submitted question is 501 characters and would be shorter after redaction
- **THEN** the system returns 422
