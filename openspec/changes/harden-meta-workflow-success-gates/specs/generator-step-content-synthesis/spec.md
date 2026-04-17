## ADDED Requirements

### Requirement: Generator synthesizes step content
Generator SHALL synthesize and populate `WorkflowStep.content` from step metadata when constructing workflow steps.

#### Scenario: Synthetic content includes key fields
- **WHEN** Generator builds a step from planner spec with `name`, `action`, `inputs`, and `outputs`
- **THEN** it SHALL construct `content` by joining those values into a non-empty string

#### Scenario: Content is present in generated model
- **WHEN** generated workflow is converted to `WorkflowModel`
- **THEN** each step SHALL include `content` unless all source fields are empty

### Requirement: Security scan sees action and IO signals
Generated step content SHALL expose action and variable tokens needed by keyword-based protocol security scans.

#### Scenario: Dangerous action keyword is visible
- **WHEN** a generated step action contains high-risk skill keywords such as `file_writer` or `shell_executor`
- **THEN** the synthesized `content` SHALL include those tokens for downstream scan detection
