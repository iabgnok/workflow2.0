## ADDED Requirements

### Requirement: Linear workflow template
The system SHALL provide `templates/example_linear.step.md` demonstrating a three-step linear flow (file_reader → llm_prompt_call → file_writer) with complete frontmatter and proper variable passing.

#### Scenario: Template is valid workflow
- **WHEN** `example_linear.step.md` is parsed by Parser
- **THEN** it SHALL produce a valid WorkflowModel with 3 steps and no validation errors

### Requirement: On-reject loop template
The system SHALL provide `templates/example_with_on_reject.step.md` demonstrating a generation-evaluation loop with on_reject routing, optional variable marking, and escalation variable passing.

#### Scenario: Template demonstrates on_reject
- **WHEN** `example_with_on_reject.step.md` is parsed
- **THEN** at least one step SHALL have an `on_reject` field pointing to an earlier step

### Requirement: Registry index separation
`index.json` SHALL be located at `workflows/registry/index.json`, separate from workflow definition files.

#### Scenario: WorkflowRegistry uses new path
- **WHEN** WorkflowRegistry initializes with default settings
- **THEN** `index_path` SHALL point to `workflows/registry/index.json`

### Requirement: Meta workflows updated to v2.0
All meta workflow files SHALL use version 2.0, mark optional variables with `?` suffix, and remove legacy prefix labels and blockquote comments.

#### Scenario: Optional variable in meta workflow
- **WHEN** `main_workflow.step.md` Step 2 is parsed
- **THEN** inputs `prev_defects` and `escalation_level` SHALL be recognized as optional
