## Context

The project already has dedicated prompt files for generator and evaluator, plus concrete workflow examples under `templates/`. In practice, generator outputs can drift from proven structures, and evaluator conclusions can become subjective when not anchored to concrete examples.

This change introduces a prompt-level contract that explicitly references templates as exemplars, so generation is more stable and review rationale is more consistent.

## Goals / Non-Goals

**Goals:**
- Make generator prompts require selecting and referencing relevant templates from `templates/` before drafting workflows.
- Make evaluator prompts include template-grounded checks and require evidence-based mismatch reasoning.
- Preserve existing hard DSL constraints while using templates as guidance.
- Add tests that fail fast when required template-reference guidance is missing from prompt files.

**Non-Goals:**
- No parser, runner, or engine runtime behavior changes.
- No new LLM provider integration or retrieval subsystem.
- No broad rewrite of template files beyond minimal referenceability improvements.

## Decisions

1. Decision: Add a shared template-reference policy to generator and evaluator prompts.
Rationale: A shared policy keeps both roles aligned on what templates mean, when to cite them, and which DSL rules remain mandatory.
Alternative considered: Put policy in only one prompt and rely on role memory. Rejected because it creates drift between generation and evaluation behavior.

2. Decision: Keep templates as exemplars, not strict code snippets.
Rationale: Direct copy behavior can overfit and reduce adaptability. The prompt will require structure borrowing while preserving task-specific content.
Alternative considered: Mandatory exact template cloning. Rejected due to low flexibility and higher mismatch in real-world workflows.

3. Decision: Add evaluator requirement to explain accept/reject using explicit template alignment evidence.
Rationale: This improves auditability and makes rejection reasons actionable for repair loops.
Alternative considered: Continue score-only output. Rejected because score-only output lacks concrete guidance.

4. Decision: Validate prompt contract with content-level tests.
Rationale: Prompt files are configuration artifacts; static assertions are sufficient and low-cost.
Alternative considered: Rely only on manual review. Rejected because regressions are easy to introduce silently.

## Risks / Trade-offs

- Risk: Over-constraining generator creativity may reduce solution diversity.
  Mitigation: Define templates as reference patterns, not mandatory full copies.

- Risk: Prompt length increases token usage.
  Mitigation: Keep reference policy concise and reusable across prompts.

- Risk: Evaluator may over-penalize valid innovations that differ from templates.
  Mitigation: Require evaluator to distinguish DSL-valid alternatives from true structural defects.

## Migration Plan

1. Update generator and evaluator prompt markdown files with template-reference sections.
2. Add or update prompt-level tests to verify required clauses and rationale format.
3. Run targeted unit and e2e tests for generator/evaluator prompt usage paths.
4. Rollback strategy: revert prompt section changes if quality regresses in smoke/e2e checks.

## Open Questions

- Should template references be mandatory in every generation, or only for complex flows with on_reject loops?
- Should evaluator output include a dedicated field listing which templates were used for comparison?
