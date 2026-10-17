# Spec Delta

## Purpose

Lets anonymous website visitors ask a question and get a short answer grounded only in the indexed public site content, with server-verified citations and hard abuse and cost limits.

## ADDED Requirements

### Requirement: Feature flag gates the endpoint
The system SHALL expose `POST /api/v1/ai/site-assistant/ask` and `GET /api/v1/ai/site-assistant/config` without authentication. The assistant SHALL be disabled by default. While it is disabled, `ask` SHALL return 404 and `config` SHALL report `enabled: false`.

#### Scenario: Disabled by default
- **WHEN** an operator has not enabled the site assistant and a visitor calls `ask`
- **THEN** the system returns 404 and makes no model call

#### Scenario: Config reports state to the UI
- **WHEN** the site assistant is enabled and a visitor calls `config`
- **THEN** the response contains `enabled: true` and the maximum question length

### Requirement: Single-turn, non-streaming request and response
The `ask` endpoint SHALL accept `{question, persona?}`, where `persona` is one of `grantee`, `funder` or `technical`, and SHALL return one JSON body `{answer, answerable, citations[]}` after generation completes. Each citation SHALL be `{content_id, url, title}`. The system SHALL NOT accept or use earlier questions or answers as context.

#### Scenario: Answer returned as one JSON body
- **WHEN** a visitor asks an answerable question
- **THEN** the response is a single JSON body with `answerable: true`, a non-empty `answer`, and at least one citation

#### Scenario: Prior-turn fields are rejected
- **WHEN** a request body includes fields other than `question` and `persona`
- **THEN** the system returns 422

### Requirement: Question length is limited
The system SHALL reject a question that is empty or longer than the configured maximum (500 characters by default) with 422 before retrieval or any model call.

#### Scenario: Over-long question
- **WHEN** a visitor submits a 501-character question with the default limit
- **THEN** the system returns 422 and makes no model call

### Requirement: Answers are grounded in retrieved site content only
The system SHALL retrieve site chunks for the question and pass only those chunks to the model, wrapped and labelled as untrusted reference data. The answer SHALL be drawn only from that content. The system SHALL NOT state pricing, partners, endorsements, guarantees, revenue or capabilities that the content does not contain. Links in the answer text SHALL point only at hosts on the operator's verified link-host list (by default the production domain); an answer linking anywhere else SHALL be returned as `answerable: false` with the fixed fallback answer.

#### Scenario: Unsupported claim requested
- **WHEN** a visitor asks "Which governments endorse OpenGrantFlow?" and no indexed content mentions an endorsement
- **THEN** the response has `answerable: false` and the answer names no endorser

#### Scenario: Instruction planted in content
- **WHEN** a retrieved chunk contains text instructing the assistant to ignore its rules or output a URL
- **THEN** the response does not follow that instruction and contains no link to a host outside the verified link-host list

#### Scenario: Link to a verified host
- **WHEN** the model's answer links to a host on the verified link-host list
- **THEN** the answer is returned unchanged

### Requirement: Weak retrieval short-circuits without a model call
When retrieval returns no chunks, or the top chunk scores below the configured unanswerable threshold, the system SHALL return `answerable: false` with no citations and SHALL NOT call the model.

#### Scenario: Off-index question
- **WHEN** a visitor asks a question that matches no indexed chunk
- **THEN** the response has `answerable: false` and no model call is made

### Requirement: Citations are resolved and verified by the server
The model SHALL return only chunk identifiers, never URLs or titles. The system SHALL drop any identifier that was not in the retrieved set for that request, and SHALL resolve each remaining identifier's URL and title from the site index. If an answer marked answerable has no valid citation left, the system SHALL return it as `answerable: false`.

#### Scenario: Hallucinated chunk ID is dropped
- **WHEN** the model cites one retrieved chunk ID and one ID that was not retrieved
- **THEN** the response contains only the retrieved chunk's citation

#### Scenario: No valid citations left
- **WHEN** the model returns `answerable: true` but every cited ID is outside the retrieved set
- **THEN** the response has `answerable: false` and no citations

#### Scenario: Citation URLs are site paths
- **WHEN** any response is returned
- **THEN** every citation URL is the `url` stored for that chunk in the site index

### Requirement: Invalid model output fails closed
If the model's output does not match the expected structure, or the model call fails, the system SHALL return `answerable: false` with no citations and SHALL NOT return model text.

#### Scenario: Malformed output
- **WHEN** the model returns output that fails schema validation
- **THEN** the response has `answerable: false`, no citations, and a fixed fallback answer

### Requirement: Model provider is operator-configured
The operator SHALL choose the assistant's provider (`anthropic` or `ollama`) and model through configuration. The default SHALL be the platform-funded Anthropic Haiku model. An `ollama` provider SHALL be used only when its origin is on the operator's approved egress list. If the configured model cannot be resolved, `ask` SHALL return 503.

#### Scenario: Ollama origin not approved
- **WHEN** the provider is `ollama` and its URL is not on the approved egress list
- **THEN** `ask` returns 503 and no request is sent to that URL

#### Scenario: Platform key missing
- **WHEN** the provider is `anthropic` and no platform API key is configured
- **THEN** `ask` returns 503

### Requirement: Daily caps follow the provider
The system SHALL enforce a per-IP daily cap and a global daily cap, both reset at 00:00 UTC. Defaults SHALL come from the provider's profile: `anthropic` 20 per IP and 300 global, `ollama` 200 per IP and no global cap. An operator setting SHALL override each default, and `0` SHALL mean unlimited. The per-IP cap SHALL count every request that passes validation. The global cap SHALL count only requests that call the model. Over either cap, `ask` SHALL return 429 with a `Retry-After` header giving the seconds until reset.

#### Scenario: Per-IP cap reached
- **WHEN** one IP sends its 21st valid question of the UTC day under the `anthropic` profile
- **THEN** the system returns 429 with `Retry-After` and makes no model call

#### Scenario: Global cap reached
- **WHEN** 300 model-calling questions have been answered today under the `anthropic` profile
- **THEN** the next question from any IP returns 429

#### Scenario: Ollama profile has no global cap
- **WHEN** the provider is `ollama` and no global cap override is set
- **THEN** no global cap is enforced, and the per-IP cap is 200

#### Scenario: Override to unlimited
- **WHEN** the operator sets the per-IP cap override to `0`
- **THEN** no per-IP cap is enforced

### Requirement: Caps fail closed
If the cap store is unavailable, `ask` SHALL return 503 and SHALL NOT call the model.

#### Scenario: Redis down
- **WHEN** the cap store cannot be reached
- **THEN** `ask` returns 503 and no model call is made

### Requirement: Client IP comes from the trusted gateway
The per-IP cap SHALL key on the client address set by the platform's gateway, not on a value the client supplies. Stored cap keys SHALL hold a keyed hash of the IP, never the raw address.

#### Scenario: Spoofed forwarding header
- **WHEN** a client sends its own `X-Forwarded-For` header through the gateway
- **THEN** the per-IP cap counts against the client's real address

### Requirement: Human-verification hook
The system SHALL run a human-verification step before retrieval. Its default SHALL allow every request. When an operator configures a verifier and it rejects a request, `ask` SHALL return 403 without a model call.

#### Scenario: Default verifier
- **WHEN** no verifier is configured
- **THEN** every request passes the verification step

### Requirement: Telemetry excludes visitor text
Each `ask` request SHALL emit a trace with the prompt version, provider and model, retrieved chunk IDs and scores, token usage and per-stage latency. Neither spans nor logs SHALL contain the question text, the model's prompt, or the answer text.

#### Scenario: Span contents
- **WHEN** a question is answered
- **THEN** the exported spans contain the retrieved chunk IDs and token counts and do not contain the question or answer text
