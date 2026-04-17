## 1. Prompt contract updates

- [ ] 1.1 Update `new_src/prompts/generator_system_v1.md` to add a template-reference policy (template selection, citation rules, and no-verbatim-copy constraint).
- [ ] 1.2 Update `new_src/prompts/evaluator_system_v1.md` to add template-grounded accept/reject rationale requirements.
- [ ] 1.3 Align shared wording between generator and evaluator prompts so template usage and hard DSL constraints are consistent.

## 2. Template referenceability updates

- [ ] 2.1 Update `new_src/agent/workflows/templates/example_linear.step.md` with parse-safe reference cues for suitable use cases and invariants.
- [ ] 2.2 Update `new_src/agent/workflows/templates/example_with_on_reject.step.md` with parse-safe loop and escalation comparison cues.
- [ ] 2.3 Verify both template files still parse into valid WorkflowModel objects after cue additions.

## 3. Tests and regression coverage

- [ ] 3.1 Add or update tests asserting generator prompt includes required template-reference clauses.
- [ ] 3.2 Add or update tests asserting evaluator prompt includes template-grounded reject rationale clauses.
- [ ] 3.3 Add or update tests asserting template cue sections exist and do not break parser validation.

## 4. End-to-end validation

- [ ] 4.1 Run targeted prompt/template related unit tests under `new_src/tests/`.
- [ ] 4.2 Run at least one meta-workflow e2e case to confirm generation quality and evaluator reasonability are improved or stable.
- [ ] 4.3 Record observed quality deltas and follow-up adjustments in change notes before apply.
