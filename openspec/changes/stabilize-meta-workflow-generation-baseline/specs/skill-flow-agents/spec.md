## ADDED Requirements

### Requirement: Reject loop defect payload is bounded
The runner SHALL pass only the latest rejection defects to the next generator turn, and MAY include a compact deduplicated summary of prior fixes.

#### Scenario: Multiple reject rounds do not accumulate raw defects
- **WHEN** a run enters the third or later reject round
- **THEN** the next generator input includes only latest-round defects plus compact prior summary instead of full historical defect list

### Requirement: Planner to generator action mapping is validated
The flow MUST validate and normalize planner `action_type` values into generator `action` values against registered skills before evaluation.

#### Scenario: Planner emits alias action_type
- **WHEN** planner output uses an alias or near-match for a registered skill
- **THEN** mapping logic normalizes it to the canonical action and records the normalization event
