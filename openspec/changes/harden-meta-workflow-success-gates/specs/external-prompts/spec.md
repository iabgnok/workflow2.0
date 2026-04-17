## MODIFIED Requirements

### Requirement: Evaluator system prompt file
The system SHALL provide `prompts/evaluator_system_v1.md` containing: four-dimension scoring with weights and thresholds, static scan override prohibition, escalation level descaling rules, and defect output format.

Updated threshold rules SHALL be:
- logic_closure: 40% weight, stage 1-2 pass threshold `>= 90`, stage 3+ pass threshold `>= 85`
- safety_gate: 30% weight, pass threshold `>= 90`
- engineering_quality: 20% weight, stage 1-2 threshold `70`, stage 3+ ignored in gate decision
- persona_adherence: 10% weight, stage 1-2 threshold `60`, stage 3+ ignored in gate decision

#### Scenario: Prompt contains updated scoring rubric
- **WHEN** the evaluator system prompt is read
- **THEN** it SHALL contain the four scoring dimensions with the updated thresholds and stage handling rules
