## ADDED Requirements

### Requirement: Sub workflow call uses infra imports
`SubWorkflowCall` SHALL import `VariableMapper` from `agent.infra.variable_mapper` (not `agent.engine`).

#### Scenario: Correct dependency direction
- **WHEN** SubWorkflowCall is imported
- **THEN** it SHALL NOT have any import from `agent.engine` package

### Requirement: Sub workflow call validates input mapping
`SubWorkflowCall` SHALL validate all required input variables exist in parent context before creating child Runner.

#### Scenario: Missing input variable
- **WHEN** step input mapping references `blueprint` but parent context lacks it
- **THEN** SubWorkflowCall SHALL raise `VariableMappingError` with the missing variable name
