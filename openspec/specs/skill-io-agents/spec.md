## ADDED Requirements

### Requirement: File reader reads from step inputs
`FileReader` SHALL read the file path from `step['inputs']` mapping instead of directly from `context.get('file_path')`.

#### Scenario: Path from step inputs
- **WHEN** step declares `Input: - source: file_path`
- **THEN** FileReader SHALL resolve `source` from context via the inputs mapping

### Requirement: File writer auto-creates directories
`FileWriter` SHALL automatically create parent directories if they don't exist before writing.

#### Scenario: Non-existent directory
- **WHEN** target path is `output/reports/summary.txt` and `output/reports/` doesn't exist
- **THEN** FileWriter SHALL create the directory chain and write the file successfully

### Requirement: File writer skips manual variable replacement
`FileWriter` SHALL NOT perform its own variable replacement. Variable injection is handled by `StepExecutor` before skill invocation.

#### Scenario: Variables already replaced
- **WHEN** StepExecutor passes content with all `{{var}}` already substituted
- **THEN** FileWriter SHALL write the content as-is without further replacement
