## ADDED Requirements

### Requirement: Centralized variable name normalization
The system SHALL provide a single `normalize_var_name(value: str) -> str` function in `protocol/utils.py` that performs: strip whitespace → strip backticks → extract template inner name from `{{...}}` → remove trailing `?` optional marker.

#### Scenario: Normalize template variable
- **WHEN** `normalize_var_name("{{  user_input? }}")` is called
- **THEN** the function SHALL return `"user_input"`

#### Scenario: Normalize plain variable
- **WHEN** `normalize_var_name("  \`file_path\`  ")` is called
- **THEN** the function SHALL return `"file_path"`

### Requirement: Centralized metadata input extraction
The system SHALL provide a single `extract_metadata_inputs(workflow: WorkflowModel) -> set[str]` function that extracts all declared input variable names from workflow metadata.

#### Scenario: Extract inputs from metadata
- **WHEN** a WorkflowModel has `metadata.inputs = ["requirement", "output_path?"]`
- **THEN** `extract_metadata_inputs()` SHALL return `{"requirement", "output_path"}`

### Requirement: Centralized optional variable detection
The system SHALL provide a single `is_optional_var(value: str) -> bool` function that returns True if the variable name ends with `?`.

#### Scenario: Detect optional variable
- **WHEN** `is_optional_var("prev_defects?")` is called
- **THEN** the function SHALL return `True`

#### Scenario: Detect required variable
- **WHEN** `is_optional_var("requirement")` is called
- **THEN** the function SHALL return `False`
