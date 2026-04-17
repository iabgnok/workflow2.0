## ADDED Requirements

### Requirement: Generator system prompt file
The system SHALL provide `prompts/generator_system_v1.md` containing: role definition, DSL format rules (frontmatter, step structure, singular Input/Output, Action backtick wrapping), variable naming conventions, two few-shot examples (linear + on_reject loop), skill whitelist injection placeholder ({skill_manifest}), repair mode rules, and prohibited behaviors.

#### Scenario: Prompt loaded by Generator
- **WHEN** Generator skill initializes with `system_prompt_path = "prompts/generator_system_v1.md"`
- **THEN** `_load_system_prompt()` SHALL return the file content as a string

### Requirement: Evaluator system prompt file
The system SHALL provide `prompts/evaluator_system_v1.md` containing: four-dimension scoring with weights and thresholds (logic_closure 40% must=100, safety_gate 30% must=100, engineering_quality 20% threshold=70, persona_adherence 10% threshold=60), static scan override prohibition, escalation level descaling rules, and defect output format.

#### Scenario: Prompt contains scoring rubric
- **WHEN** the evaluator system prompt is read
- **THEN** it SHALL contain the four scoring dimensions with their weights and pass/fail thresholds

### Requirement: Planner system prompt file
The system SHALL provide `prompts/planner_system_v1.md` containing: role definition as macro architecture decomposer, split judgment criteria, WorkflowBlueprint output field specifications, and prohibited behaviors.

#### Scenario: Prompt defines output structure
- **WHEN** the planner system prompt is read
- **THEN** it SHALL specify the WorkflowBlueprint fields (workflow_name, handoff_contracts, main_flow_steps, etc.)

### Requirement: Prompt file caching
`LLMAgentSpec._load_system_prompt()` SHALL cache file contents after first read.

#### Scenario: File read only once
- **WHEN** a skill calls `_load_system_prompt()` multiple times
- **THEN** the file system SHALL be accessed only once
