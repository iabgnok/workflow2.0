## ADDED Requirements

### Requirement: ExecutionHooks protocol with five covenants
`ExecutionHooks` SHALL be an async base class with four hook methods. All hooks SHALL follow five covenants: async, no meaningful return (except on_step_before), exception-isolated, FIFO execution order, context read-only.

#### Scenario: Hook exception does not crash Runner
- **WHEN** `on_step_after()` raises an unexpected exception
- **THEN** Runner SHALL log the error and continue to the next step

#### Scenario: on_step_before can skip a step
- **WHEN** `on_step_before()` returns `StepHookResult(skip=True)`
- **THEN** Runner SHALL skip execution of that step and proceed to the next

### Requirement: StepHookResult data class
The system SHALL provide `StepHookResult` with a `skip: bool = False` field, returned by `on_step_before()`.

#### Scenario: Default does not skip
- **WHEN** `StepHookResult()` is created with defaults
- **THEN** `skip` SHALL be `False`
