## MODIFIED Requirements

### Requirement: Protocol error flowback
ChampionTracker SHALL merge protocol defects into `prev_defects` both before evaluator review and during end-of-run registration checks.

#### Scenario: Pre-evaluator protocol defects are injected
- **WHEN** `on_step_before()` is called for evaluator step and `final_artifact` exists in context
- **THEN** ChampionTracker SHALL run protocol checks and append detected defects into `prev_defects` before evaluator execution

#### Scenario: Registration fails with protocol errors
- **WHEN** `register_workflow_model()` returns a ProtocolReport with errors at run end
- **THEN** errors SHALL be converted via `errors_as_defects()` and appended to context `prev_defects`
