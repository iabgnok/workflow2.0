## ADDED Requirements

### Requirement: Meta workflow final status derivation
Runner SHALL derive final run status from evaluator and replay outcomes for meta workflows.

#### Scenario: Non-meta workflow remains success
- **WHEN** run context does not contain `evaluator_report`
- **THEN** Runner SHALL return `status = "success"`

#### Scenario: Evaluator rejects
- **WHEN** run context contains `evaluator_report` and parsed report status is not `APPROVED`
- **THEN** Runner SHALL return `status = "rejected"`

#### Scenario: Approved but replay missing
- **WHEN** evaluator report status is `APPROVED` and context does not contain `generated_workflow_replay`
- **THEN** Runner SHALL return `status = "approved_unverified"`

#### Scenario: Approved and replay succeeds
- **WHEN** evaluator report status is `APPROVED` and `generated_workflow_replay.status == "success"`
- **THEN** Runner SHALL return `status = "success"`

#### Scenario: Approved and replay fails
- **WHEN** evaluator report status is `APPROVED` and replay status is not `success`
- **THEN** Runner SHALL return `status = "replay_failed"`
