## ADDED Requirements

### Requirement: Generic Skill base class
The system SHALL provide a `Skill[InputT, OutputT]` generic base class with class-level metadata: name, description, when_to_use, do_not_use_when, idempotency, retry_policy, input_type, output_type.

#### Scenario: Skill metadata accessible
- **WHEN** a skill class declares `name = "file_reader"` and `idempotency = IdempotencyLevel.L0`
- **THEN** `SkillRegistry` SHALL read these class variables for policy lookup and manifest generation

### Requirement: LLMAgentSpec provides structured LLM access
`LLMAgentSpec` SHALL provide `_get_structured_llm(schema)` for building structured-output LLM clients and `_load_system_prompt()` for reading external prompt files with caching.

#### Scenario: System prompt loaded and cached
- **WHEN** `_load_system_prompt()` is called twice
- **THEN** the file SHALL be read only once; the second call returns the cached result

### Requirement: schema_summary generates SkillCard text
Each `Skill` subclass SHALL provide a `schema_summary() -> str` class method that generates human-readable metadata text suitable for LLM prompt injection.

#### Scenario: SkillCard includes input/output schema
- **WHEN** a skill has `input_type = FileReaderInput` with field `file_path: str`
- **THEN** `schema_summary()` SHALL include the field name and type in the output text
