## ADDED Requirements

### Requirement: Meta workflow quality gate enforcement
The system SHALL mark a meta workflow run as quality-pass only when evaluator status is `APPROVED` and score is greater than or equal to a configured minimum threshold.

#### Scenario: Approved run meets threshold
- **WHEN** a run returns evaluator status `APPROVED` and score `>= min_quality_score`
- **THEN** the run is recorded as quality-pass and can be counted as successful baseline output

#### Scenario: Rejected or low-score run fails quality gate
- **WHEN** evaluator status is not `APPROVED` or score is below `min_quality_score`
- **THEN** the run is recorded as quality-fail and cannot be counted as successful baseline output

### Requirement: Quality gate threshold configuration
The system MUST expose `min_quality_score` as configuration with a default value of 60 for baseline environments.

#### Scenario: Missing explicit threshold uses default
- **WHEN** runtime settings do not provide `min_quality_score`
- **THEN** the quality gate uses default threshold value `60`
