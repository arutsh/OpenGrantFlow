# ai-provider-settings Specification

## Purpose
TBD - created by archiving change superuser-cross-tenant-access. Update Purpose after archive.
## Requirements
### Requirement: AI provider settings are scoped by customer, not by individual user
The system SHALL store and look up AI provider key/model configuration (`UserProviderKey`) by the acting user's `customer_id`, not by their individual `user_id`. Any admin-or-above user acting for a customer — including a superuser impersonating that customer — SHALL see and modify the same set of configs, and the same default, as any other admin-or-above user of that customer. A customer may have zero, one, or multiple configs; the customer-scoping applies to the whole set, not to a single provider-keyed row.

#### Scenario: One admin sees another admin's configured key
- **WHEN** an admin of a customer configures an AI provider key, and a different admin of the same customer subsequently views AI settings
- **THEN** the second admin sees the key as configured, not as unconfigured

#### Scenario: Impersonating superuser and the customer's own admin see the same configuration
- **WHEN** a superuser impersonating a customer configures an AI provider key, and the customer's own admin subsequently views AI settings
- **THEN** the admin sees the key as configured, matching what the superuser set

#### Scenario: Admins of the same customer share the same set of configs and default
- **WHEN** one admin of a customer adds a second config and marks it default
- **THEN** any other admin-or-above user of that same customer sees both configs and the same one marked default

### Requirement: An organization can save multiple configs per provider
The system SHALL allow a customer to save more than one `UserProviderKey` row for the same provider, each independently created and deleted, optionally carrying a `label` for display purposes.

#### Scenario: Second config for the same provider
- **WHEN** an admin saves a new Anthropic config for an organization that already has one Anthropic config configured
- **THEN** both configs are stored and both remain independently visible and usable, not overwritten

### Requirement: Exactly one saved config is the organization's default
Among a customer's saved configs, at most one SHALL be marked default at any time. When resolving which provider/model to use for a request that doesn't specify one, the system SHALL use the config marked default, not the most recently modified one.

#### Scenario: Setting a new default unsets the previous one
- **WHEN** an admin marks a non-default config as default
- **THEN** that config becomes the default and the previously-default config is no longer marked default

#### Scenario: Resolution uses the default, not recency
- **WHEN** a customer has multiple configured configs and a non-default one was modified most recently
- **THEN** requests that don't specify a model resolve to the config marked default, not the most recently modified one

### Requirement: Deleting the default config is always allowed; a replacement default is an optional convenience
The system SHALL allow deletion of a customer's default config unconditionally. The request MAY optionally name another existing config of that customer to promote to default in the same operation; if no replacement is named, the customer is simply left with no default. Enabling the platform-funded model as a default is a separate, independent action (see platform-fallback requirement below) and is not a delete-time choice.

#### Scenario: Delete default without a replacement succeeds
- **WHEN** an admin requests deletion of the org's current default config without naming a replacement
- **THEN** the deletion succeeds and the customer is left with no default set

#### Scenario: Delete default with a named replacement succeeds
- **WHEN** an admin requests deletion of the org's current default config and names another of the org's existing configs as the new default
- **THEN** the named config becomes the new default and the deleted config is removed, in the same operation

#### Scenario: Deleting an organization's last remaining config is allowed
- **WHEN** an admin deletes a customer's only remaining config
- **THEN** the deletion succeeds and the customer is left with no configs and no default, without requiring a replacement

### Requirement: Only a superuser may set the platform-funded model as an organization's default
Choosing GrantFlow's platform-funded model as a customer's explicit default (rather than one of its own BYOK configs) SHALL require the acting user to have the `superuser` role. An `admin` acting for the customer SHALL NOT be able to enable this on their own.

#### Scenario: Admin attempts to enable platform-funded default
- **WHEN** a user with role `admin` requests that the platform-funded model be set as their organization's default
- **THEN** the system rejects the request with a 403

#### Scenario: Superuser enables platform-funded default
- **WHEN** a user with role `superuser` requests that the platform-funded model be set as an organization's default
- **THEN** the request succeeds and that organization's default resolves to the platform-funded model until changed

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

