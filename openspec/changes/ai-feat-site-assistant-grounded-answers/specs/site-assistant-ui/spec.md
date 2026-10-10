# Spec Delta

## Purpose

The question box on the public Home page that sends visitor questions to the site assistant and shows grounded answers with links to their sources, falling back to browse links whenever no answer is available.

## ADDED Requirements

### Requirement: Assistant box appears on Home only when enabled
The Home page SHALL show the assistant box only when the site assistant's config reports `enabled: true`. If the config is disabled or cannot be loaded, the Home page SHALL render without the box and without an error.

#### Scenario: Assistant disabled
- **WHEN** a visitor opens Home and the config reports `enabled: false`
- **THEN** no assistant box is shown and the rest of the page renders normally

#### Scenario: Config request fails
- **WHEN** the config request returns an error
- **THEN** no assistant box is shown and no error is displayed

### Requirement: Visitor can ask with an optional persona
The box SHALL offer a persona toggle (`grantee`, `funder`, `technical`, or none) and a question field limited to the configured maximum length. Submitting SHALL send the question and the selected persona, and SHALL disable the submit control until the response arrives.

#### Scenario: Persona sent with the question
- **WHEN** a visitor selects `funder` and submits a question
- **THEN** the request carries `persona: funder`

#### Scenario: Length limit enforced in the field
- **WHEN** the configured maximum is 500 characters
- **THEN** the field accepts no more than 500 characters

### Requirement: Answers show their sources
For `answerable: true`, the box SHALL show the answer text followed by one link per citation, labelled with the citation title and pointing at its URL. The answer text SHALL be rendered as plain text, never as HTML.

#### Scenario: Cited answer
- **WHEN** the response has `answerable: true` and two citations
- **THEN** the box shows the answer and two source links to the cited URLs

#### Scenario: Markup in answer text
- **WHEN** the answer text contains HTML tags
- **THEN** the tags are shown as literal text and not interpreted

### Requirement: Browse-instead fallback
When the response has `answerable: false`, or the request fails with 429, 503 or any other error, the box SHALL show a short message and links to the public site's main pages instead of an answer.

#### Scenario: Unanswerable question
- **WHEN** the response has `answerable: false`
- **THEN** the box shows the "couldn't find that" message with browse links

#### Scenario: Daily cap reached
- **WHEN** the request returns 429
- **THEN** the box shows a "try again tomorrow" message with browse links

### Requirement: Visitors are told where questions go
The box SHALL show a short notice that questions are processed by an AI provider, with a link to the privacy policy.

#### Scenario: Notice visible before asking
- **WHEN** the assistant box is shown
- **THEN** the AI-processing notice and privacy-policy link are visible without submitting a question
