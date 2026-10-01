## ADDED Requirements

### Requirement: Custom provider endpoints are limited to an operator-approved policy
The system SHALL accept a custom `base_url` for a provider config only when the URL's origin (scheme, host, port) is on the operator-configured approved list. The approved list SHALL be settable only through service configuration, never through any tenant-facing API, including by admins or superusers acting through the API. The system SHALL reject a `base_url` for providers that do not use one. Only `http` and `https` schemes SHALL be accepted, and URLs with embedded credentials SHALL be rejected.

#### Scenario: Admin saves an internal service as a provider URL
- **WHEN** an admin saves an Ollama config with `base_url` `http://users:8000`
- **THEN** the request is rejected with 422 and no config is stored

#### Scenario: Admin saves an approved endpoint
- **WHEN** an admin saves an Ollama config whose `base_url` matches an approved origin
- **THEN** the config is stored

#### Scenario: Tenant cannot widen the policy
- **WHEN** any caller, including a superuser, uses the tenant-facing settings API
- **THEN** no endpoint exists that adds or changes an approved origin

### Requirement: Outbound provider requests enforce the policy at request time
The system SHALL re-check every outbound request to a custom provider endpoint against the policy at the moment it is sent. The system SHALL fail closed for stored configs that do not match. The system SHALL NOT follow HTTP redirects on those requests. For approved origins not explicitly allowed to be private, the system SHALL reject the request when the host resolves to any non-public address. The connection SHALL be made to the address that was validated, so that a change in DNS answers between validation and connection cannot redirect it.

#### Scenario: Stored config predating the policy
- **WHEN** a chat or extraction request resolves a stored config whose `base_url` is not approved
- **THEN** the request is not sent and the caller receives the same "no usable AI provider" outcome as a misconfigured provider

#### Scenario: Redirect to an internal address
- **WHEN** an approved public endpoint responds with a 3xx redirect to `http://169.254.169.254/`
- **THEN** the redirect is not followed and the call fails

#### Scenario: DNS rebinding
- **WHEN** an approved public-only hostname resolves to a public address at save time but to `10.0.0.5` at request time
- **THEN** the request is refused before any connection to `10.0.0.5` is made

#### Scenario: Operator-run private Ollama
- **WHEN** a config uses an approved origin flagged as private-allowed (e.g. `http://ollama:11434`)
- **THEN** the request is sent even though the host resolves to a private address
