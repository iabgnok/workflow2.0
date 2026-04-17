## ADDED Requirements

### Requirement: Execution observer tracks pressure telemetry
`ExecutionObserver` SHALL sample context pressure ratio at step boundaries and flush stats to StateStore.

#### Scenario: Pressure recorded per step
- **WHEN** a step completes execution
- **THEN** observer SHALL record the context pressure ratio for that step

#### Scenario: Stats flushed on completion
- **WHEN** workflow completes or Runner encounters an error
- **THEN** observer SHALL flush accumulated stats to `state_store.save_run_meta()`
