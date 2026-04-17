## ADDED Requirements

### Requirement: Resume strategy loads checkpoint state
`ResumeStrategy.resume(run_id, state_store, context)` SHALL load persisted state and return the start step ID.

#### Scenario: New run starts at step 1
- **WHEN** run_id is None
- **THEN** SHALL return `1`

#### Scenario: Resumed run starts at next step
- **WHEN** run_id exists and last successful step was 3
- **THEN** SHALL return `4` and context SHALL be hydrated with persisted variables
