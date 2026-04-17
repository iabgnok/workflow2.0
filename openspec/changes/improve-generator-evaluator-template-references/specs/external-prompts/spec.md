## MODIFIED Requirements

### Requirement: Generator system prompt file
The system SHALL provide `prompts/generator_system_v1.md` containing: role definition, DSL format rules (frontmatter, step structure, singular Input/Output, Action backtick wrapping), variable naming conventions, two few-shot examples (linear + on_reject loop), skill whitelist injection placeholder ({skill_manifest}), repair mode rules, prohibited behaviors, and a template-reference policy that explicitly guides selection and citation of suitable files under `templates/` as structural exemplars.

#### Scenario: Prompt loaded by Generator
- **WHEN** Generator skill initializes with `system_prompt_path = "prompts/generator_system_v1.md"`
- **THEN** `_load_system_prompt()` SHALL return the file content as a string

#### Scenario: Prompt contains template-reference policy
- **WHEN** the generator system prompt is read
- **THEN** it SHALL define how to choose and reference template examples from `templates/` before drafting a workflow
- **AND** it SHALL require template usage to preserve hard DSL constraints rather than copy template content verbatim

### Requirement: Evaluator system prompt file
The system SHALL provide `prompts/evaluator_system_v1.md` containing: four-dimension scoring with weights and thresholds (logic_closure 40% must=100, safety_gate 30% must=100, engineering_quality 20% threshold=70, persona_adherence 10% threshold=60), static scan override prohibition, escalation level descaling rules, defect output format, and template-grounded review guidance that explains accept/reject outcomes against relevant `templates/` patterns.

#### Scenario: Prompt contains scoring rubric
- **WHEN** the evaluator system prompt is read
- **THEN** it SHALL contain the four scoring dimensions with their weights and pass/fail thresholds

#### Scenario: Evaluator requires template-grounded rationale
- **WHEN** Evaluator returns a reject decision
- **THEN** the rationale SHALL identify at least one concrete mismatch relative to a relevant template pattern or explicit DSL rule
- **AND** the rationale SHALL avoid generic feedback that cannot guide repair
