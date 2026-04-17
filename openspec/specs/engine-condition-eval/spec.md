## ADDED Requirements

### Requirement: Condition evaluation with simpleeval sandbox
`ConditionEvaluator.eval(condition, context)` SHALL evaluate condition expressions using simpleeval and return `(should_skip: bool, reason: str)`.

#### Scenario: No condition means no skip
- **WHEN** condition is `None`
- **THEN** SHALL return `(False, "")`

#### Scenario: Falsy condition result skips step
- **WHEN** condition is `"retry_count > 0"` and context has `retry_count = 0`
- **THEN** SHALL return `(True, "条件不满足: retry_count > 0")`

#### Scenario: Undefined variable skips step gracefully
- **WHEN** condition references a variable not in context
- **THEN** SHALL return `(True, "条件变量未就绪: ...")` instead of crashing
