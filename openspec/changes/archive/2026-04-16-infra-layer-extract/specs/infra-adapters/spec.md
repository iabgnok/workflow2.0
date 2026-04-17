## ADDED Requirements

### Requirement: VariableMappingError exception
`variable_mapper.py` SHALL define a `VariableMappingError` exception for input/output mapping failures in sub_workflow_call.

#### Scenario: Missing source variable
- **WHEN** `map_inputs()` cannot find a required source variable in parent context
- **THEN** it SHALL raise `VariableMappingError` with the missing variable name

### Requirement: Context manager reset methods
`context_manager.py` SHALL provide `perform_soft_reset(context, max_history)` and `perform_hard_reset(context)` methods for explicit context pressure management.

#### Scenario: Soft reset trims chat history
- **WHEN** `perform_soft_reset(context, max_history=8)` is called and chat_history has 20 entries
- **THEN** chat_history SHALL be trimmed to the most recent 8 entries

#### Scenario: Hard reset clears chat history
- **WHEN** `perform_hard_reset(context)` is called
- **THEN** chat_history SHALL be set to an empty list

### Requirement: WorkflowRegistry register_workflow_model
`workflow_registry.py` SHALL provide `register_workflow_model(model: WorkflowModel)` that validates via DryRun before registration.

#### Scenario: DryRun failure blocks registration
- **WHEN** a WorkflowModel fails DryRun contract check
- **THEN** `register_workflow_model()` SHALL NOT write to index.json and SHALL return the failure report
