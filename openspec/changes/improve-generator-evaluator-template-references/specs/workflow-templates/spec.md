## MODIFIED Requirements

### Requirement: Linear workflow template
The system SHALL provide `templates/example_linear.step.md` demonstrating a three-step linear flow (file_reader -> llm_prompt_call -> file_writer) with complete frontmatter, proper variable passing, and concise reference cues indicating when this template is an appropriate structural exemplar for generation and evaluation.

#### Scenario: Template is valid workflow
- **WHEN** `example_linear.step.md` is parsed by Parser
- **THEN** it SHALL produce a valid WorkflowModel with 3 steps and no validation errors

#### Scenario: Template provides reference cues
- **WHEN** generator or evaluator prompt guidance references linear template usage
- **THEN** `example_linear.step.md` SHALL contain parse-safe cues describing applicable use cases and structural invariants

### Requirement: On-reject loop template
The system SHALL provide `templates/example_with_on_reject.step.md` demonstrating a generation-evaluation loop with on_reject routing, optional variable marking, escalation variable passing, and concise reference cues indicating how loop and recovery semantics should be compared during evaluation.

#### Scenario: Template demonstrates on_reject
- **WHEN** `example_with_on_reject.step.md` is parsed
- **THEN** at least one step SHALL have an `on_reject` field pointing to an earlier step

#### Scenario: Template defines loop comparison cues
- **WHEN** evaluator checks a workflow containing iterative repair loops
- **THEN** the template SHALL expose parse-safe cues for expected loop routing and escalation semantics used in review rationale
