## ADDED Requirements

### Requirement: Generator eliminates text round-trip
`LLMGeneratorCall` SHALL output `StructuredWorkflowArtifact` via Pydantic structured LLM output and convert directly to `WorkflowModel` without Markdown rendering or re-parsing.

#### Scenario: Generator produces WorkflowModel
- **WHEN** Generator executes with a valid blueprint
- **THEN** the output SHALL contain a `WorkflowModel` object (or data that can construct one) without intermediate Markdown

### Requirement: Generator uses skill manifest
Generator's prompt SHALL inject the full skill manifest (structured SkillCard descriptions) instead of plain skill name list.

#### Scenario: Skill manifest in prompt
- **WHEN** Generator builds its prompt
- **THEN** the `{skill_manifest}` placeholder SHALL be replaced with output from `SkillRegistry.build_skill_manifest()`

### Requirement: Evaluator static scan on WorkflowModel
`LLMEvaluatorCall` SHALL perform static scan on `WorkflowModel` object fields (not Markdown text) as the primary scan path.

#### Scenario: Static scan catches violation
- **WHEN** a WorkflowModel has a step with unknown action
- **THEN** static scan SHALL report violation and return REJECTED without invoking LLM

### Requirement: Planner returns dict not JSON string
`LLMPlannerCall` SHALL return `workflow_blueprint` as a dict (via `model_dump()`) instead of a JSON string (via `model_dump_json()`).

#### Scenario: Blueprint is dict type
- **WHEN** Planner executes successfully
- **THEN** `output["workflow_blueprint"]` SHALL be a Python dict, not a JSON string

### Requirement: LLM Prompt skill removes Mock mode
`LLMPromptCall` SHALL NOT include a Mock/fallback mode. If LLM client initialization fails, the skill SHALL NOT be registered.

#### Scenario: No mock fallback
- **WHEN** LLM client cannot be initialized
- **THEN** `LLMPromptCall` registration SHALL fail or the skill SHALL raise on execution
