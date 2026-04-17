## ADDED Requirements

### Requirement: Abstract state store interface
The system SHALL provide an `AbstractStateStore` abstract base class defining the contract for all state store implementations, with 9 async methods.

#### Scenario: Interface enforces implementation
- **WHEN** a subclass of `AbstractStateStore` does not implement all 9 methods
- **THEN** instantiation SHALL raise `TypeError`

### Requirement: JSON-only serialization
`SQLiteStateStore` SHALL use JSON serialization for all context data. Pickle SHALL NOT be used.

#### Scenario: Non-JSON-serializable value
- **WHEN** context contains a non-JSON-serializable value (e.g., a set)
- **THEN** the store SHALL convert it to a JSON-compatible type (e.g., list) before saving

### Requirement: LLM client registry with caching
The system SHALL provide an `LLMClientRegistry` singleton that caches LLM client instances by (provider, model, temperature, json_mode) tuple.

#### Scenario: Same config returns cached client
- **WHEN** `get_or_create(provider="gemini", model="flash", temperature=0.0, json_mode=False)` is called twice
- **THEN** the same client instance SHALL be returned both times

### Requirement: Skill registry recursive scanning
`SkillRegistry` SHALL recursively scan `skills/llm/`, `skills/io/`, and `skills/flow/` subdirectories for skill classes.

#### Scenario: Skill in subdirectory is discovered
- **WHEN** `skills/llm/generator.py` defines a class `LLMGeneratorCall` with `execute_step` method
- **THEN** `SkillRegistry.scan()` SHALL register it under its declared `name` attribute

### Requirement: Skill manifest generation
`SkillRegistry` SHALL provide `build_skill_manifest() -> str` that generates a structured text listing all registered skills with their metadata (name, description, when_to_use, do_not_use_when, input/output schemas).

#### Scenario: Manifest includes all skills
- **WHEN** 7 skills are registered
- **THEN** `build_skill_manifest()` SHALL return text containing all 7 skills' metadata
