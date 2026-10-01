## ADDED Requirements

### Requirement: External data in history is never presented as model output
`POST /ai/decide` SHALL accept conversation history turns marked as external data. It SHALL pass them to the model as clearly delimited, request-side content identified as untrusted data, and SHALL NOT convert them into assistant or model-response messages. The system prompt SHALL NOT direct the model to take tool parameters from anything other than the user's own messages.

#### Scenario: External-data turn in history
- **WHEN** a decide request's history contains an external-data turn
- **THEN** the message list sent to the provider contains that content only inside a request-side part labelled as external data, and no model-response part contains it
