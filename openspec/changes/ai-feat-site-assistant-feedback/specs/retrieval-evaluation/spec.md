# Spec Delta

## MODIFIED Requirements

### Requirement: Golden dataset format
The system SHALL define a golden dataset as a list of entries, each with a unique `id`, a `question`, `expected_content_ids` (empty when `answerable` is `false`), a `persona`, a `category`, an `answerable` boolean, and a `source` of `authored` or `production`. An entry without `source` SHALL be read as `authored`. Every `expected_content_ids` value SHALL exist in the site index. A `production` entry SHALL carry no record ID, country or timestamp from the question it came from.

#### Scenario: Answerable entry has expected content
- **WHEN** a golden dataset entry has `answerable: true`
- **THEN** it carries at least one `content_id` in `expected_content_ids`

#### Scenario: Unanswerable entry has no expected content
- **WHEN** a golden dataset entry has `answerable: false`
- **THEN** `expected_content_ids` is empty

#### Scenario: Existing entries default to authored
- **WHEN** an entry has no `source` field
- **THEN** it is loaded as `source: authored`

#### Scenario: Production entry with leaked provenance
- **WHEN** an entry has `source: production` and also a record ID, country or timestamp field
- **THEN** loading the dataset fails and names the entry

### Requirement: Recall and MRR reported per category
The system SHALL compute Recall@1, Recall@3, Recall@5, and Mean Reciprocal Rank (MRR) over the dataset's answerable entries, both overall and broken down per `category` and per `source`.

#### Scenario: Recall@k counts a hit
- **WHEN** an answerable entry's top-`k` results include at least one of its `expected_content_ids`
- **THEN** it counts as a hit for Recall@k

#### Scenario: MRR uses the first relevant rank
- **WHEN** an answerable entry's first matching result appears at rank `r`
- **THEN** that entry contributes `1/r` to MRR

#### Scenario: Production-sourced breakdown
- **WHEN** the dataset holds at least one `production` entry
- **THEN** the report shows Recall and MRR for `production` entries separately from `authored` ones
