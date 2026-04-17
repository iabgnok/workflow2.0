"""Settings 类单元测试。"""
import pytest

from config.settings import Settings


class TestSettingsDefaults:
    """4.1 验证 Settings 类的默认值正确。"""

    def test_llm_provider_default(self):
        s = Settings()
        assert s.llm_provider == "gemini"

    def test_gemini_model_default(self):
        s = Settings()
        assert s.gemini_model == "gemini-2.0-flash-lite"

    def test_deepseek_model_default(self):
        s = Settings()
        assert s.deepseek_model == "deepseek-chat"

    def test_deepseek_base_url_default(self):
        s = Settings()
        assert s.deepseek_base_url == "https://api.deepseek.com/v1"

    def test_openai_model_default(self):
        s = Settings()
        assert s.openai_model == "gpt-4o-mini"

    def test_context_window_tokens_default(self):
        s = Settings()
        assert s.context_window_tokens == 120000

    def test_context_soft_ratio_default(self):
        s = Settings()
        assert s.context_soft_ratio == pytest.approx(0.60)

    def test_context_hard_ratio_default(self):
        s = Settings()
        assert s.context_hard_ratio == pytest.approx(0.80)

    def test_soft_reset_max_history_default(self):
        s = Settings()
        assert s.soft_reset_max_history == 10

    def test_min_quality_score_default(self):
        s = Settings()
        assert s.min_quality_score == 60

    def test_structured_validation_max_retries_default(self):
        s = Settings()
        assert s.structured_validation_max_retries == 1

    def test_empty_string_defaults(self):
        s = Settings()
        for field in ("llm_model", "llm_api_key", "llm_base_url",
                      "gemini_api_key", "deepseek_api_key",
                      "openai_api_key", "openai_base_url"):
            assert getattr(s, field) == "", f"{field} should default to empty string"


class TestSettingsEnvOverride:
    """4.2 验证环境变量能正确覆盖默认值。"""

    def test_llm_provider_override(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        s = Settings()
        assert s.llm_provider == "deepseek"

    def test_gemini_api_key_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "abc123")
        s = Settings()
        assert s.gemini_api_key == "abc123"

    def test_context_window_tokens_override(self, monkeypatch):
        monkeypatch.setenv("CONTEXT_WINDOW_TOKENS", "200000")
        s = Settings()
        assert s.context_window_tokens == 200000

    def test_context_soft_ratio_override(self, monkeypatch):
        monkeypatch.setenv("CONTEXT_SOFT_RATIO", "0.5")
        s = Settings()
        assert s.context_soft_ratio == pytest.approx(0.5)

    def test_db_path_override(self, monkeypatch):
        monkeypatch.setenv("DB_PATH", "/data/workflow.db")
        s = Settings()
        assert s.db_path == "/data/workflow.db"

    def test_min_quality_score_override(self, monkeypatch):
        monkeypatch.setenv("MIN_QUALITY_SCORE", "75")
        s = Settings()
        assert s.min_quality_score == 75

    def test_case_insensitive_env(self, monkeypatch):
        monkeypatch.setenv("llm_provider", "openai")
        s = Settings()
        assert s.llm_provider == "openai"


class TestDefaultWorkflowInputs:
    """4.3 验证 default_workflow_inputs 字段结构。"""

    def test_has_all_five_keys(self):
        s = Settings()
        keys = set(s.default_workflow_inputs.keys())
        assert keys == {"repo_path", "readme_path", "output_path", "retry_count", "max_retries"}

    def test_readme_path_default(self):
        s = Settings()
        assert s.default_workflow_inputs["readme_path"] == "README.md"

    def test_output_path_default(self):
        s = Settings()
        assert s.default_workflow_inputs["output_path"] == "output.txt"

    def test_retry_count_default(self):
        s = Settings()
        assert s.default_workflow_inputs["retry_count"] == 0

    def test_max_retries_default(self):
        s = Settings()
        assert s.default_workflow_inputs["max_retries"] == 3

    def test_repo_path_default_is_empty_string(self):
        s = Settings()
        assert s.default_workflow_inputs["repo_path"] == ""

    def test_override_via_constructor(self):
        custom = {"repo_path": "/my/repo", "readme_path": "docs/README.md",
                  "output_path": "out.txt", "retry_count": 1, "max_retries": 5}
        s = Settings(default_workflow_inputs=custom)
        assert s.default_workflow_inputs["repo_path"] == "/my/repo"
        assert s.default_workflow_inputs["max_retries"] == 5


class TestPathFieldEmptyString:
    """4.4 验证路径字段空字符串行为。"""

    def test_db_path_default_empty(self):
        s = Settings()
        assert s.db_path == ""

    def test_workflows_root_default_empty(self):
        s = Settings()
        assert s.workflows_root == ""

    def test_skills_root_default_empty(self):
        s = Settings()
        assert s.skills_root == ""

    def test_prompts_root_default_empty(self):
        s = Settings()
        assert s.prompts_root == ""

    def test_empty_path_is_falsy(self):
        s = Settings()
        assert not s.db_path, "empty db_path should be falsy — consuming code should derive path"

    def test_explicit_path_is_truthy(self, monkeypatch):
        monkeypatch.setenv("WORKFLOWS_ROOT", "/workflows")
        s = Settings()
        assert s.workflows_root == "/workflows"
        assert s.workflows_root, "explicit workflows_root should be truthy"
