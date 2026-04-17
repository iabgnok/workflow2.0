# Meta Workflow Rollout Toggles

## Runtime Toggles

- `MIN_QUALITY_SCORE`:
  - Default: `60`
  - Meaning: Meta workflow only counts as quality-pass when evaluator score is `>= MIN_QUALITY_SCORE`.

- `STRUCTURED_VALIDATION_MAX_RETRIES`:
  - Default: `1`
  - Meaning: Generator deterministic precheck can retry generation up to `N` times before passing defects to evaluator precheck rejection path.

## Operational Signals

- `context.generator_validation_summary`: latest deterministic validation summary.
- `context.generator_validation_feedback`: reason emitted when structured validation retries are exhausted.
- `context.action_normalization_audit`: action normalization/repair records.
- `context.prev_defects_summary`: latest-round defects summary (source, previous_count, latest_count, machine_only).

## Rollback Order

When production stability regresses, rollback in this order:

1. Raise `MIN_QUALITY_SCORE` gate only after disabling strict checks, or temporarily lower it for stability.
2. Set `STRUCTURED_VALIDATION_MAX_RETRIES=0` to disable extra precheck regeneration loops.
3. Revert Generator/Planner prompts to previous stable prompt snapshots.
4. Disable machine-fix-first reject behavior and restore legacy reject counter if needed.

## Validation Checklist

- Generator prompt contains schema-first JSON contract and no markdown output template.
- Planner prompt enforces `registered_skills` whitelist for `action_type`.
- Evaluator short-circuits when `pre_evaluator_defects` is present.
- E2E assertions verify `APPROVED` and `score >= MIN_QUALITY_SCORE`.
