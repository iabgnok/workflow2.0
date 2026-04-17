## Why

Generator and evaluator quality currently varies because prompt guidance is rule-heavy but not consistently anchored to concrete workflow templates. Adding explicit template references can improve generation consistency and make evaluator judgments more grounded and explainable.

## What Changes

- Extend `prompts/generator_system_v1.md` with instructions to reference suitable files under `templates/` as structural examples before drafting workflows.
- Extend `prompts/evaluator_system_v1.md` with template-grounded review criteria, requiring explicit mismatch reasoning against referenced template patterns.
- Define a shared template-reference policy for when to cite template names, what can be borrowed, and what must still follow hard DSL constraints.
- Add or update tests to verify both prompts contain template-reference rules and evaluator rationale requirements.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `external-prompts`: Generator and evaluator prompt requirements are expanded to include template-reference guidance and evidence-based review language.
- `workflow-templates`: Existing templates gain an explicit contract as reference exemplars for generation and evaluation, not only static examples.

## Impact

- Affected files: `new_src/prompts/generator_system_v1.md`, `new_src/prompts/evaluator_system_v1.md`, and prompt-related tests under `new_src/tests/`.
- No new runtime dependencies expected.
- Behavior impact: more stable workflow outputs and more consistent evaluator decisions, with clearer rationale for accept/reject outcomes.
