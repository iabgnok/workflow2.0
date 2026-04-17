## ADDED Requirements

### Requirement: Single step execution
`StepExecutor` SHALL execute a single step given step dict and context dict, returning output dict. Its pipeline is: variable injection → pre-assertion → skill lookup → execute_with_policy → post-assertion.

#### Scenario: Successful step execution
- **WHEN** a step with action "file_reader" and valid inputs is executed
- **THEN** StepExecutor SHALL return the skill output dict with all declared output variables

#### Scenario: Unknown skill raises SkillNotFoundError
- **WHEN** step action is "nonexistent_skill"
- **THEN** StepExecutor SHALL raise `SkillNotFoundError`

### Requirement: StepExecutor does not handle routing or state
StepExecutor SHALL NOT evaluate conditions, persist state, or make routing decisions (on_reject).

#### Scenario: No state persistence calls
- **WHEN** StepExecutor.execute() completes
- **THEN** it SHALL NOT call any StateStore methods
