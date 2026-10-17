# Spec Delta

## Purpose

Measures `site-retrieval`'s quality against a committed golden dataset and fails CI when quality regresses, so retrieval changes are judged by evidence instead of impressions.

## ADDED Requirements

### Requirement: Golden dataset format
The system SHALL define a golden dataset as a list of entries, each with a unique `id`, a `question`, `expected_content_ids` (empty when `answerable` is `false`), a `persona`, a `category`, and an `answerable` boolean.

#### Scenario: Answerable entry has expected content
- **WHEN** a golden dataset entry has `answerable: true`
- **THEN** it carries at least one `content_id` in `expected_content_ids`

#### Scenario: Unanswerable entry has no expected content
- **WHEN** a golden dataset entry has `answerable: false`
- **THEN** `expected_content_ids` is empty

### Requirement: Recall and MRR reported per category
The system SHALL compute Recall@1, Recall@3, Recall@5, and Mean Reciprocal Rank (MRR) over the dataset's answerable entries, both overall and broken down per `category`.

#### Scenario: Recall@k counts a hit
- **WHEN** an answerable entry's top-`k` results include at least one of its `expected_content_ids`
- **THEN** it counts as a hit for Recall@k

#### Scenario: MRR uses the first relevant rank
- **WHEN** an answerable entry's first matching result appears at rank `r`
- **THEN** that entry contributes `1/r` to MRR

### Requirement: Unanswerable accuracy reported separately
The system SHALL report, for entries with `answerable: false`, the fraction whose top result's score falls below a committed threshold, as a metric distinct from Recall/MRR.

#### Scenario: Correctly flagged unanswerable
- **WHEN** an `answerable: false` entry's top result score is below the threshold
- **THEN** it counts toward unanswerable accuracy

#### Scenario: False positive on unanswerable entry
- **WHEN** an `answerable: false` entry's top result score is at or above the threshold
- **THEN** it does not count toward unanswerable accuracy, and is distinguishable in the report from a correct flag

### Requirement: Full-context token baseline reported
The system SHALL report the token cost of the entire indexed corpus alongside the token cost of a typical top-k retrieval, so retrieval's savings are visible in the eval report.

#### Scenario: Full-context baseline present in report
- **WHEN** an eval run completes
- **THEN** the report includes the whole-corpus token count and the average top-k token count for the run

### Requirement: CI gate enforces a committed floor per metric
The system SHALL compare every reported metric (overall and per category) against a floor recorded in a committed baseline file, and SHALL fail the run when any metric falls below its floor.

#### Scenario: Metric at or above floor passes
- **WHEN** a reported metric is greater than or equal to its baseline floor
- **THEN** the gate passes for that metric

#### Scenario: Metric below floor fails the run
- **WHEN** a reported metric is below its baseline floor
- **THEN** the eval run fails
