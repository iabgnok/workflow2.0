## ADDED Requirements

### Requirement: Generator prompt is schema-first
The generator system prompt MUST describe output requirements using structured artifact fields and JSON examples, and MUST NOT require markdown workflow text formatting.

#### Scenario: Generator prompt uses JSON-only output guidance
- **WHEN** the generator prompt is rendered for a run
- **THEN** it contains field-level JSON guidance aligned with `StructuredWorkflowArtifact` and excludes markdown formatting rules

### Requirement: Planner prompt enforces registered skill whitelist
The planner prompt SHALL include `registered_skills` and SHALL constrain `action_type` planning to values mapped to registered skills.

#### Scenario: Planner receives skill whitelist
- **WHEN** planner prompt context is built
- **THEN** `registered_skills` is injected and `action_type` instructions require selecting from the whitelist

### Requirement: Generator prompt includes evaluator rubric summary
The generator prompt MUST include a concise summary of evaluator scoring dimensions used for acceptance.

#### Scenario: Generator sees acceptance dimensions
- **WHEN** generator prompt is rendered
- **THEN** prompt text includes evaluator scoring dimensions and pass expectations
