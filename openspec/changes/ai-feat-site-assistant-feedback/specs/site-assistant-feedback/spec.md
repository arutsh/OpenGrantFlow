# Spec Delta

## Purpose

Keeps a privacy-limited record of each site-assistant question and the visitor's feedback on its answer for a fixed period, so failures can be reviewed and turned into permanent eval cases.

## ADDED Requirements

### Requirement: Personal details are removed from questions
Before retrieval, the model call and storage, the system SHALL replace the following in the question with a fixed placeholder per type: email addresses, phone numbers, IBANs, payment-card-like digit runs, IPv4 and IPv6 addresses, and URL query strings. Redaction SHALL be best effort and SHALL NOT be claimed to catch names or free-text personal details. The unredacted question SHALL NOT be stored, logged, or sent to the model.

#### Scenario: Email in a question
- **WHEN** a visitor asks "Can jane.doe@example.org get a demo?"
- **THEN** the model, the retriever and the stored record see "Can [email] get a demo?"

#### Scenario: Question without personal details
- **WHEN** a question contains none of the listed patterns
- **THEN** it is used unchanged

#### Scenario: Ordinary numbers are kept
- **WHEN** a question contains a short number such as "Can I add 3 currencies?"
- **THEN** the number is not redacted

### Requirement: Every question is recorded
Every `ask` request that passes validation, the per-IP cap, human verification and model resolution SHALL write one question record holding:
- the redacted question
- the persona
- the visitor's country code
- the retrieved chunk IDs with their scores
- the outcome: `answered`, `refused`, `short_circuited` or `failed`
- the served answer text, the cited chunk IDs, the provider, model and prompt version (absent when the model was not called)
- the creation time

The record SHALL NOT hold the IP address, any hash of it, a user or session identifier, or request headers.

#### Scenario: Short-circuited question is recorded
- **WHEN** a question's retrieval is too weak to call the model
- **THEN** a record is written with outcome `short_circuited`, the retrieved IDs and scores, and no answer, model or prompt version

#### Scenario: Rejected requests are not recorded
- **WHEN** a request returns 422, 429, 403 or 503
- **THEN** no question record is written

### Requirement: Recording never blocks an answer
If writing the question record fails, the system SHALL still return the answer, without an answer ID, and SHALL log the failure without the question or answer text.

#### Scenario: Database write fails
- **WHEN** the record insert raises
- **THEN** the visitor receives the answer with `answer_id: null`, and an error log names the failure type only

### Requirement: Country from a local lookup only
The visitor's country SHALL be resolved from the client address set by the platform's gateway, using a locally stored IP-to-country database, as an ISO 3166-1 alpha-2 code. No external service SHALL be called per request. When the database is missing or has no match, the country SHALL be stored as unknown and the request SHALL proceed.

#### Scenario: Lookup database missing
- **WHEN** the IP-to-country database file is not present
- **THEN** records store an unknown country, answers are unaffected, and one warning is logged at startup

### Requirement: Visitor feedback on an answer
The system SHALL expose `POST /api/v1/ai/site-assistant/feedback` without authentication, accepting `{answer_id, rating, reason?}`.
- `rating` SHALL be `up` or `down`.
- `reason` SHALL be one of `incorrect`, `did_not_answer`, `outdated`, `missing_information` or `other`, and SHALL be accepted only with `down`.
- No free-text field SHALL be accepted.
- A later submission for the same answer SHALL replace the earlier one.
- An unknown or purged `answer_id` SHALL return 404.
- The endpoint SHALL be disabled (404) whenever the assistant is disabled.
- Feedback SHALL count against its own per-IP daily cap.

#### Scenario: Thumbs down with a reason
- **WHEN** a visitor submits `{answer_id, rating: down, reason: outdated}` for a stored answer
- **THEN** the system returns 204 and the record holds that rating and reason

#### Scenario: Changing a rating
- **WHEN** a visitor rates an answer `down` and then `up`
- **THEN** the record holds only `up`, with no reason

#### Scenario: Reason with a thumbs up
- **WHEN** a request has `rating: up` and a `reason`
- **THEN** the system returns 422

#### Scenario: Extra text field
- **WHEN** a request includes a `comment` field
- **THEN** the system returns 422

### Requirement: 90-day retention
Question records and their feedback SHALL be deleted automatically once older than 90 days, by a job that runs at least daily. Deleting a record SHALL delete its feedback.

#### Scenario: Old record purged
- **WHEN** the purge job runs and a record was created 91 days ago
- **THEN** the record and its feedback no longer exist

#### Scenario: Recent record kept
- **WHEN** the purge job runs and a record was created 89 days ago
- **THEN** the record is unchanged

### Requirement: Review and promotion through a CLI only
Records SHALL be readable only through an operator command-line tool run where the ai service's database is reachable, never through an HTTP endpoint. The tool SHALL export records filtered by date range, outcome and rating to a file. A separate local step SHALL turn an exported record into a golden-dataset entry, but only after the operator confirms or rewrites the question text and supplies the expected content IDs, category and answerability. The promoted entry SHALL NOT carry the record's ID, country or timestamp.

#### Scenario: Export negative feedback
- **WHEN** the operator exports records rated `down` from the last 30 days
- **THEN** the file holds those records' redacted questions, outcomes, retrieved IDs, answers, ratings and reasons, and no other records

#### Scenario: Promoting a record
- **WHEN** the operator promotes an exported record and confirms the question, expected sources and category
- **THEN** one entry is appended to the golden dataset with source `production` and no record ID, country or timestamp

#### Scenario: Unknown content ID during promotion
- **WHEN** the operator supplies an expected content ID that is not in the site index
- **THEN** promotion is refused and the dataset is unchanged
