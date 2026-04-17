## ADDED Requirements

### Requirement: Direct WorkflowModel validation
`ProtocolService` SHALL provide a `validate_workflow_model(model: WorkflowModel, registered_skills: list[str], available_context: dict)` method that combines security scan, gatekeeper validation, and dry run on a WorkflowModel object directly (without file path).

#### Scenario: Valid WorkflowModel passes all checks
- **WHEN** a well-formed WorkflowModel with registered actions and correct variable flow is validated
- **THEN** the method SHALL return a combined result with no errors

#### Scenario: Invalid action detected
- **WHEN** a WorkflowModel contains a step with action "nonexistent_skill"
- **THEN** the gatekeeper portion SHALL report a WF_UNKNOWN_ACTIONS error

### Requirement: WorkflowModel security scanning
`security_scan.py` SHALL provide a `scan_workflow_model(model: WorkflowModel) -> SecurityScanResult` function that scans step content fields for DANGER/CONFIRM keywords and checks `require_confirm` field.

#### Scenario: Danger keyword in step content
- **WHEN** a WorkflowStep has content containing "rm -rf /" without [DANGER] tag
- **THEN** `scan_workflow_model()` SHALL report a security violation

### Requirement: WorkflowModel serialization to Markdown
`WorkflowModel` SHALL provide a `to_markdown() -> str` method that renders the model to standard `.step.md` format for persistence to disk.

#### Scenario: Round-trip consistency
- **WHEN** a WorkflowModel is serialized via `to_markdown()` and the resulting text is parsed back
- **THEN** the parsed model SHALL be semantically equivalent to the original

### Requirement: WorkflowStep require_confirm field
`WorkflowStep` SHALL include a `require_confirm: bool = False` field that records the [CONFIRM] marker from DSL parsing, replacing text-based detection in security_scan.

#### Scenario: CONFIRM tag parsed to field
- **WHEN** a step's Action line is `**Action**: \`file_writer\` [CONFIRM]`
- **THEN** the parsed WorkflowStep SHALL have `require_confirm = True` and `action = "file_writer"`
