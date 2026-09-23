# Spec Delta

## Purpose

Provides budget service with a locally persisted, read-through cache of customer/organisation details (name, `is_donor`, `is_ngo`), so lookups by `customer_id` survive process restarts instead of depending on an in-memory-only cache.

## ADDED Requirements

### Requirement: Customer details are read-through cached locally
The system SHALL resolve customer details (name, `is_donor`, `is_ngo`) for a given `customer_id` by first checking a local store, and only calling the users service over HTTP on a cache miss.

#### Scenario: Cache hit
- **WHEN** customer details for a given `customer_id` already exist in the local store
- **THEN** the system returns them without making an HTTP call to the users service

#### Scenario: Cache miss
- **WHEN** customer details for a given `customer_id` do not exist in the local store
- **THEN** the system fetches them via HTTP from the users service, persists them locally, and returns them

### Requirement: Cached customer details persist across restarts
The system SHALL persist cached customer details in a local table (not only in-process memory), so a service restart does not discard previously resolved entries.

#### Scenario: Lookup after restart
- **WHEN** a customer's details were cached before a service restart
- **THEN** a subsequent lookup for that `customer_id` after restart is served from the local store without an HTTP call

### Requirement: Staleness is accepted, not actively invalidated
The system SHALL NOT proactively invalidate or refresh cached customer details when the source customer record changes. Staleness is an accepted trade-off given how infrequently these fields change; active invalidation is out of scope unless this becomes a demonstrated problem.

#### Scenario: Source customer record changes after caching
- **WHEN** a customer's name or `is_donor`/`is_ngo` flags change in the users service after being cached in budget service
- **THEN** budget service continues returning the previously cached values until that entry is naturally refreshed (e.g. via a future cache-miss path), with no dedicated invalidation mechanism required
