## ADDED Requirements

### Requirement: Deterministic pre-evaluator validation
The generation pipeline MUST run deterministic validation for action legality and protocol integrity before invoking evaluator scoring.

#### Scenario: Artifact fails deterministic validation
- **WHEN** generated workflow contains unregistered action names or protocol violations
- **THEN** the pipeline reports validation defects before evaluator scoring begins

### Requirement: Deterministic auto-repair for fixable issues
The pipeline SHALL auto-repair fixable validation issues (for example, closest-match skill normalization) and MUST emit a repair audit record.

#### Scenario: Fixable action typo is auto-repaired
- **WHEN** generated action differs from a registered skill by a supported fuzzy-match threshold
- **THEN** pipeline replaces it with the canonical skill name and records a repair audit entry
