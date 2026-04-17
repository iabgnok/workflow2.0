## ADDED Requirements

### Requirement: E2E baseline test includes quality assertions
Meta workflow E2E baseline tests MUST assert evaluator approval status and minimum score threshold in addition to runtime success.

#### Scenario: Runtime success but quality reject fails test
- **WHEN** workflow status is success but evaluator status is not `APPROVED` or score is below threshold
- **THEN** the E2E baseline test fails with explicit quality-gate failure details

### Requirement: Success-rate reporting uses quality-pass runs
Success-rate metrics SHALL count only runs that satisfy quality gate criteria as successful outcomes.

#### Scenario: Success-rate excludes low-quality successes
- **WHEN** batch statistics are computed for meta workflow success rate
- **THEN** runs below quality gate are excluded from successful count even if execution completed
