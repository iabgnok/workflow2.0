## ADDED Requirements

### Requirement: Settings class provides typed configuration
The system SHALL provide a `Settings` class inheriting from `pydantic_settings.BaseSettings` that centralizes all configuration fields with Python type annotations and default values.

#### Scenario: Settings loads from environment variables
- **WHEN** environment variable `LLM_PROVIDER` is set to `"deepseek"`
- **THEN** `settings.llm_provider` SHALL return `"deepseek"`

#### Scenario: Settings loads from .env file
- **WHEN** a `.env` file contains `GEMINI_API_KEY=abc123` and no environment variable overrides it
- **THEN** `settings.gemini_api_key` SHALL return `"abc123"`

#### Scenario: Settings provides defaults when no env is set
- **WHEN** no `CONTEXT_WINDOW_TOKENS` environment variable or .env entry exists
- **THEN** `settings.context_window_tokens` SHALL return `120000`

### Requirement: Module-level singleton access
The system SHALL expose a module-level singleton `settings` instance, accessible via `from config.settings import settings` throughout the project.

#### Scenario: Singleton consistency
- **WHEN** two different modules import `settings`
- **THEN** both SHALL reference the same `Settings` instance

### Requirement: LLM configuration fields
The system SHALL provide configuration fields for all supported LLM providers: Gemini, DeepSeek, and OpenAI, including provider selection, model name, API key, and base URL.

#### Scenario: Provider-specific defaults
- **WHEN** `llm_provider` is `"gemini"` and `llm_model` is empty
- **THEN** the LLM factory SHALL use `settings.gemini_model` (default: `"gemini-2.0-flash-lite"`)

### Requirement: Engine parameter configuration
The system SHALL provide configuration fields for engine runtime parameters: context window token budget, soft/hard pressure ratios, and soft reset max history.

#### Scenario: Context pressure thresholds
- **WHEN** settings are loaded with defaults
- **THEN** `context_soft_ratio` SHALL be `0.60` and `context_hard_ratio` SHALL be `0.80`

### Requirement: Path configuration with dynamic defaults
The system SHALL provide path configuration fields (db_path, workflows_root, skills_root, prompts_root) that default to empty strings, allowing consuming code to derive paths dynamically when empty.

#### Scenario: Empty path triggers dynamic derivation
- **WHEN** `settings.db_path` is empty string
- **THEN** the consuming module (e.g., StateStore) SHALL derive the path relative to its own `__file__` location

#### Scenario: Explicit path overrides dynamic derivation
- **WHEN** environment variable `DB_PATH` is set to `/data/workflow.db`
- **THEN** `settings.db_path` SHALL return `/data/workflow.db` and consuming code SHALL use it directly

### Requirement: Default workflow inputs
The system SHALL provide a `default_workflow_inputs` dict field containing the five standard runtime defaults (repo_path, readme_path, output_path, retry_count, max_retries), replacing the hardcoded values in `infer_inputs.py`.

#### Scenario: Default workflow inputs available
- **WHEN** `with_runtime_input_defaults()` is called
- **THEN** it SHALL read default values from `settings.default_workflow_inputs` instead of hardcoded values
