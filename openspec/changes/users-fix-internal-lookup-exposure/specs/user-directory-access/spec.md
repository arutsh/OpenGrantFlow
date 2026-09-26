## Purpose

Defines who may read user and customer records from the users service, how internal service-to-service lookups are authenticated, and which internal endpoints must never be reachable from the public gateway.

## ADDED Requirements

### Requirement: Internal lookup endpoints are not publicly routed
The public API gateway (every deployed gateway configuration) SHALL NOT route requests to the users service's internal batch-lookup endpoints (`users/by_ids`, `customers/by_ids`).

#### Scenario: Anonymous internet caller hits the batch user lookup
- **WHEN** a caller on the public internet sends `POST /api/v1/users/by_ids/` through the gateway
- **THEN** the gateway rejects the request (404 or 403) without forwarding it to the users service

#### Scenario: Anonymous internet caller hits the batch customer lookup
- **WHEN** a caller on the public internet sends `POST /api/v1/customers/by_ids/` through the gateway
- **THEN** the gateway rejects the request without forwarding it

### Requirement: Internal lookup endpoints require a service credential
The users service SHALL reject any request to an internal batch-lookup endpoint that does not carry a valid internal service credential. When no credential is configured, the endpoint SHALL reject every request (fail closed).

#### Scenario: Missing credential on the internal network
- **WHEN** a request reaches `POST /api/users/by_ids/` directly (bypassing the gateway) with no service credential
- **THEN** the service responds 401 and returns no records

#### Scenario: Legitimate service caller
- **WHEN** the budget service calls `POST /api/users/by_ids/` with a valid service credential and a list of ids
- **THEN** the service returns exactly the records for those ids

### Requirement: Empty id lists return no records
A batch lookup with an empty id list SHALL return an empty result, never an unfiltered result.

#### Scenario: Empty list
- **WHEN** an authorized caller sends `POST /api/users/by_ids/` or `POST /api/customers/by_ids/` with body `[]`
- **THEN** the response is an empty list

### Requirement: Single-user reads are authenticated and tenant-scoped
`GET /api/users/{user_id}` SHALL require either an authenticated user token or a valid internal service credential. With a user token, it SHALL return the record only when the caller is that user or an `admin` of the same company, including an admin acting through an impersonation token for that company. Otherwise it SHALL respond as not found.

#### Scenario: Anonymous single-user read
- **WHEN** an unauthenticated caller requests `GET /api/users/{user_id}`
- **THEN** the request is rejected with 401

#### Scenario: Cross-tenant single-user read
- **WHEN** an authenticated user of company A requests the record of a user in company B
- **THEN** the service responds 404

#### Scenario: Same-company admin read
- **WHEN** an admin of company A requests the record of another user in company A
- **THEN** the record is returned
