## ADDED Requirements

### Requirement: Protocol issues convertible to defect format
Each `ProtocolIssue` SHALL provide a `to_defect_dict()` method that outputs a dict compatible with the Generator's `prev_defects` format: `{"location": str, "type": "PROTOCOL_ERROR", "reason": str, "suggestion": str}`.

#### Scenario: Convert gatekeeper error to defect
- **WHEN** a ProtocolIssue with code="WF_UNKNOWN_ACTIONS", message="Unknown action: fake_skill", location="step:3", suggestion="Use registered skill" calls `to_defect_dict()`
- **THEN** the result SHALL be `{"location": "step:3", "type": "PROTOCOL_ERROR", "reason": "Unknown action: fake_skill", "suggestion": "Use registered skill"}`

### Requirement: Batch error-to-defect conversion
`ProtocolReport` SHALL provide an `errors_as_defects() -> list[dict]` method that converts all error-level issues to defect dicts.

#### Scenario: Multiple errors converted
- **WHEN** a ProtocolReport contains 2 errors and 1 warning
- **THEN** `errors_as_defects()` SHALL return a list of exactly 2 defect dicts (warnings excluded)
