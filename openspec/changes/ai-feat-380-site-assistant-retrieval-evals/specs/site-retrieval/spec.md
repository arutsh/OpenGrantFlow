# Spec Delta

## Purpose

Turns a natural-language query into a ranked list of indexed site sections, using Postgres full-text search with an optional persona boost — no LLM, no embeddings.

## ADDED Requirements

### Requirement: Query returns ranked chunks
The system SHALL accept a free-text query and return `site_chunks` ranked by `ts_rank_cd` against the chunk's `tsvector`, most relevant first.

#### Scenario: Query ranks matching chunks above non-matching ones
- **WHEN** a query shares vocabulary with chunk A's text but not chunk B's
- **THEN** chunk A ranks above chunk B in the returned results

#### Scenario: No matching chunks
- **WHEN** a query matches no chunk's `tsvector`
- **THEN** the system returns an empty result list

### Requirement: Persona boost on matching chunks
The system SHALL accept an optional persona (`grantee`, `funder`, or `technical`) and, when supplied, SHALL apply a multiplicative score boost to chunks whose `personas` includes it, without excluding chunks that have no `personas` or a non-matching one.

#### Scenario: Persona-matching chunk is boosted
- **WHEN** a query is issued with persona `grantee` and two chunks score equally on `ts_rank_cd`, one tagged `personas: [grantee]` and one with no `personas`
- **THEN** the `grantee`-tagged chunk ranks above the untagged chunk

#### Scenario: No persona supplied
- **WHEN** a query is issued with no persona
- **THEN** ranking uses `ts_rank_cd` alone, with no boost applied

### Requirement: Result count is bounded
The system SHALL accept a caller-supplied `top_k` and SHALL return at most `top_k` results.

#### Scenario: top_k limits results
- **WHEN** a query matches more chunks than `top_k`
- **THEN** only the `top_k` highest-ranked chunks are returned
