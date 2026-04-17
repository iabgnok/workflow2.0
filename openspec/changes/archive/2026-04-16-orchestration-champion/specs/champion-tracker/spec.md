## ADDED Requirements

### Requirement: Champion composite reuse
ChampionTracker SHALL check for existing champion by composite key (requirement_fingerprint + blueprint_fingerprint) on run start.

#### Scenario: Champion found and reused
- **WHEN** a run starts with the same requirement and blueprint as a previously APPROVED champion
- **THEN** ChampionTracker SHALL hydrate context with champion data and set `__reuse_champion__ = True`

#### Scenario: No matching champion
- **WHEN** no champion matches the composite key
- **THEN** execution SHALL proceed normally without skipping

### Requirement: Step skip via hooks
ChampionTracker SHALL skip Designer (step 2) and Evaluator (step 3) when `__reuse_champion__` is True and champion data is available.

#### Scenario: Designer skipped on reuse
- **WHEN** `__reuse_champion__` is True and step.id == 2 with final_artifact in context
- **THEN** `on_step_before()` SHALL return `StepHookResult(skip=True)`

### Requirement: Champion update on evaluation
ChampionTracker SHALL update champion record when evaluator returns APPROVED and score >= existing score.

#### Scenario: Higher score updates champion
- **WHEN** evaluator reports APPROVED with score 92 and existing champion has score 85
- **THEN** champion_json SHALL be updated with the new artifact and score

#### Scenario: Lower score keeps existing champion
- **WHEN** evaluator reports APPROVED with score 70 and existing champion has score 85
- **THEN** champion_json SHALL NOT be updated

### Requirement: Workflow registration on completion
ChampionTracker SHALL register the generated workflow via WorkflowRegistry on workflow completion when the evaluator report status is APPROVED.

#### Scenario: Successful registration
- **WHEN** workflow completes with APPROVED evaluator report
- **THEN** ChampionTracker SHALL call `workflow_registry.register_workflow_model()` and save registration audit

### Requirement: Protocol error flowback
ChampionTracker SHALL merge protocol registration errors into `prev_defects` for Generator's next retry cycle.

#### Scenario: Registration fails with protocol errors
- **WHEN** `register_workflow_model()` returns a ProtocolReport with errors
- **THEN** errors SHALL be converted via `errors_as_defects()` and appended to context `prev_defects`
