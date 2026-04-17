## 1. Prompt contract alignment

- [x] 1.1 Rewrite `new_src/prompts/generator_system_v1.md` to be JSON/schema-first and remove markdown workflow formatting instructions.
- [x] 1.2 Add `registered_skills` whitelist guidance and evaluator scoring-dimension summary to generator prompt context.
- [x] 1.3 Update `new_src/prompts/planner_system_v1.md` to require `action_type` selection from registered skills.
- [x] 1.4 Add prompt regression fixtures/tests that fail if markdown-output-only instructions reappear in generator prompt.

## 2. Planner-to-generator action normalization

- [x] 2.1 Implement `action_type -> action` normalization utility with strict whitelist validation.
- [x] 2.2 Add nearest-match normalization for fixable action typos and emit structured normalization audit records.
- [x] 2.3 Wire normalization into generator pre-evaluator pipeline so invalid actions cannot reach evaluator unchanged.

## 3. Deterministic validation and protocol flowback

- [x] 3.1 Add a deterministic pre-evaluator validation step that runs action legality and protocol integrity checks.
- [x] 3.2 Classify validation defects into `machine-fixable` and `model-fixable` categories.
- [x] 3.3 Update reject policy to attempt deterministic repair for machine-fixable defects before consuming generator retry budget.
- [x] 3.4 Add unit tests covering classification, repair path, and fallback-to-regeneration behavior.

## 4. Reject loop context hygiene

- [x] 4.1 Refactor `runner._reject()` to pass only latest-round defects to the next generation turn.
- [x] 4.2 Add deduplicated prior-round repair summary payload and remove unbounded defect accumulation.
- [x] 4.3 Add tests validating multi-round runs do not grow defect prompts unboundedly.

## 5. Quality gates and e2e assertions

- [x] 5.1 Introduce `min_quality_score` setting (default 60) and apply it to quality-pass decision logic.
- [x] 5.2 Update `tests/e2e/test_meta_workflow_generation.py` to assert evaluator status `APPROVED` and score `>= min_quality_score`.
- [x] 5.3 Ensure success-rate statistics count only quality-pass runs and expose failure reason details.
- [x] 5.4 Normalize test/log output encoding to UTF-8 for readable CI and local diagnostics.

## 6. Stabilization and rollout

- [x] 6.1 Add configurable retry limits and error-reason feedback for structured-output validation failures.
- [x] 6.2 Run targeted e2e suite (baseline + success-rate) and capture before/after pass-rate comparison.
- [x] 6.3 Document rollout toggles and rollback order for prompt changes, deterministic repair, and quality-threshold gates.
