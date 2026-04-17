## ADDED Requirements

### Requirement: Protocol errors are classified for flowback
Protocol validation failures MUST be classified into machine-fixable and model-fixable categories and fed back through the reject path with category tags.

#### Scenario: Mixed protocol defects are classified
- **WHEN** validation detects both missing required fields and semantic ordering errors
- **THEN** defects are returned with category tags indicating machine-fixable or model-fixable

### Requirement: Retry policy consumes classified defects
The reject strategy SHALL use defect categories to decide whether to run deterministic repair first or request a new model generation turn.

#### Scenario: Machine-fixable defect bypasses immediate re-generation
- **WHEN** all defects in a round are machine-fixable
- **THEN** deterministic repair is attempted before consuming another generator retry budget
