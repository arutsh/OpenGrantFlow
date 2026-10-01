# Spec Delta

## Purpose

Covers Mistral AI as a BYOK hosted-API provider option, and the correctness of the mechanism that determines what any hosted-API provider requires (a key, a base URL, neither) when the provider has no distinctive key format.

## ADDED Requirements

### Requirement: Mistral is available as a BYOK provider
The system SHALL offer Mistral as a selectable AI provider for customer-supplied keys, with its own catalog of selectable models, following the same encrypted-key-at-rest and per-customer-scoping behavior as other hosted-API providers.

#### Scenario: Admin configures a Mistral key
- **WHEN** an admin saves a valid Mistral API key and selects a Mistral model
- **THEN** the config is stored encrypted, becomes usable for AI requests, and is not tied to a base URL

#### Scenario: Invalid Mistral key is rejected
- **WHEN** an admin submits a Mistral key that Mistral's API rejects as invalid
- **THEN** the system returns a 422 and does not save the config

#### Scenario: Model not in Mistral's catalog is rejected
- **WHEN** an admin submits a model name that isn't in Mistral's seeded catalog
- **THEN** the system returns a 422, matching how an invalid model is rejected for any other provider

### Requirement: Provider key/base-URL requirements come from an explicit flag, not key format
The system SHALL determine whether saving a provider config requires an API key, and whether an unspecified `base_url` should default to a local address, from an explicit per-provider flag — not by inferring either from whether the provider defines a `key_prefix`. A provider that requires a key but has no fixed key-prefix format SHALL still be rejected when no key is supplied, and SHALL NOT have its `base_url` defaulted to a local address.

#### Scenario: Keyed provider with no fixed prefix rejects a missing key
- **WHEN** an admin submits a config for a provider that requires a key (e.g. Mistral) without supplying a key
- **THEN** the system returns a 422, the same as it would for any other key-requiring provider

#### Scenario: Keyed provider with no fixed prefix does not get a local default base URL
- **WHEN** an admin saves a valid config for a provider that requires a key and defines no `key_prefix`
- **THEN** the stored config's `base_url` is left unset, not defaulted to `http://localhost:11434`
