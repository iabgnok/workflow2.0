"""
LLMAgentSpec 单元测试。

覆盖：
- _load_system_prompt() 正确读取文件内容
- 缓存行为：文件系统仅被访问一次
- settings.prompts_root 路径拼接正确
- 错误路径：system_prompt_path 未设置 / 文件不存在
"""
import os
from unittest.mock import mock_open, patch

import pytest

from agent.skills.base import LLMAgentSpec
from config.settings import Settings


# ── 工具：构造指向真实 prompts/ 目录的 Settings ─────────────────────────────

def _real_prompts_root() -> str:
    """返回项目中实际存在的 new_src/prompts/ 目录的绝对路径。"""
    this_dir = os.path.dirname(__file__)                 # new_src/tests/skills/
    return os.path.normpath(os.path.join(this_dir, "..", "..", "prompts"))


# ── 测试辅助子类 ──────────────────────────────────────────────────────────────

class GeneratorSpec(LLMAgentSpec):
    system_prompt_path = "generator_system_v1.md"


class EvaluatorSpec(LLMAgentSpec):
    system_prompt_path = "evaluator_system_v1.md"


class PlannerSpec(LLMAgentSpec):
    system_prompt_path = "planner_system_v1.md"


class NoPathSpec(LLMAgentSpec):
    pass  # system_prompt_path 未设置


# ── 任务 2.1：_load_system_prompt() 正确加载文件内容 ─────────────────────────

class TestLoadSystemPrompt:
    def test_generator_prompt_loads_successfully(self):
        """Generator 系统 Prompt 文件能被成功加载，返回非空字符串。"""
        spec = GeneratorSpec()
        with patch("agent.skills.base.settings", Settings(prompts_root=_real_prompts_root())):
            content = spec._load_system_prompt()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_evaluator_prompt_loads_successfully(self):
        """Evaluator 系统 Prompt 文件能被成功加载。"""
        spec = EvaluatorSpec()
        with patch("agent.skills.base.settings", Settings(prompts_root=_real_prompts_root())):
            content = spec._load_system_prompt()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_planner_prompt_loads_successfully(self):
        """Planner 系统 Prompt 文件能被成功加载。"""
        spec = PlannerSpec()
        with patch("agent.skills.base.settings", Settings(prompts_root=_real_prompts_root())):
            content = spec._load_system_prompt()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_generator_prompt_contains_role_definition(self):
        """Generator Prompt 包含角色定义关键词。"""
        spec = GeneratorSpec()
        with patch("agent.skills.base.settings", Settings(prompts_root=_real_prompts_root())):
            content = spec._load_system_prompt()
        assert "Generator" in content

    def test_evaluator_prompt_contains_scoring_dimensions(self):
        """Evaluator Prompt 包含四维评分规则。"""
        spec = EvaluatorSpec()
        with patch("agent.skills.base.settings", Settings(prompts_root=_real_prompts_root())):
            content = spec._load_system_prompt()
        assert "logic_closure" in content
        assert "safety_gate" in content
        assert "engineering_quality" in content
        assert "persona_adherence" in content

    def test_planner_prompt_contains_blueprint_fields(self):
        """Planner Prompt 包含 WorkflowBlueprint 字段规范。"""
        spec = PlannerSpec()
        with patch("agent.skills.base.settings", Settings(prompts_root=_real_prompts_root())):
            content = spec._load_system_prompt()
        assert "workflow_name" in content
        assert "main_flow_steps" in content


# ── 任务 2.2：缓存行为——文件系统仅访问一次 ───────────────────────────────────

class TestCachingBehavior:
    def test_file_read_only_once_on_multiple_calls(self):
        """连续调用 _load_system_prompt() 多次，open() 只被调用一次。"""
        fake_content = "# Fake Prompt Content"
        spec = GeneratorSpec()

        with patch("builtins.open", mock_open(read_data=fake_content)) as mock_file, \
             patch("agent.skills.base.settings", Settings(prompts_root="/fake/root")):
            result1 = spec._load_system_prompt()
            result2 = spec._load_system_prompt()
            result3 = spec._load_system_prompt()

        assert result1 == fake_content
        assert result2 == fake_content
        assert result3 == fake_content
        # 文件系统仅访问一次
        assert mock_file.call_count == 1

    def test_cache_is_instance_level(self):
        """不同实例之间缓存互不影响。"""
        spec_a = GeneratorSpec()
        spec_b = GeneratorSpec()

        fake_content_a = "# Prompt A"
        fake_content_b = "# Prompt B"

        with patch("agent.skills.base.settings", Settings(prompts_root="/root")):
            with patch("builtins.open", mock_open(read_data=fake_content_a)):
                result_a = spec_a._load_system_prompt()

            with patch("builtins.open", mock_open(read_data=fake_content_b)):
                result_b = spec_b._load_system_prompt()

        assert result_a == fake_content_a
        assert result_b == fake_content_b

    def test_cache_persists_across_calls(self):
        """首次加载后，即使 open 抛出异常，缓存仍能返回正确内容。"""
        fake_content = "# Cached Prompt"
        spec = GeneratorSpec()

        with patch("agent.skills.base.settings", Settings(prompts_root="/fake/root")):
            # 首次加载
            with patch("builtins.open", mock_open(read_data=fake_content)):
                first = spec._load_system_prompt()

            # 第二次调用：open 被替换为会抛出异常的 mock，但缓存应命中
            with patch("builtins.open", side_effect=OSError("should not be called")):
                second = spec._load_system_prompt()

        assert first == fake_content
        assert second == fake_content


# ── 任务 2.3：settings.prompts_root 路径拼接正确 ─────────────────────────────

class TestPromptsRootPathJoining:
    def test_absolute_path_is_constructed_from_prompts_root(self):
        """_load_system_prompt() 使用 settings.prompts_root 拼接绝对路径。"""
        fake_root = "/custom/prompts/root"
        expected_path = os.path.join(fake_root, "generator_system_v1.md")
        fake_content = "# content"
        spec = GeneratorSpec()

        with patch("agent.skills.base.settings", Settings(prompts_root=fake_root)), \
             patch("builtins.open", mock_open(read_data=fake_content)) as mock_file:
            spec._load_system_prompt()

        mock_file.assert_called_once_with(expected_path, encoding="utf-8")

    def test_prompts_root_env_var_override(self, monkeypatch, tmp_path):
        """环境变量 PROMPTS_ROOT 能正确覆盖默认路径。"""
        custom_root = str(tmp_path)
        monkeypatch.setenv("PROMPTS_ROOT", custom_root)

        s = Settings()
        assert s.prompts_root == custom_root

    def test_default_prompts_root_points_to_new_src_prompts(self):
        """默认 prompts_root 为空字符串，由消费方动态推导。"""
        s = Settings()
        assert s.prompts_root == ""


# ── 错误路径 ─────────────────────────────────────────────────────────────────

class TestErrorPaths:
    def test_raises_value_error_when_path_not_set(self):
        """system_prompt_path 未设置时抛出 ValueError。"""
        spec = NoPathSpec()
        with pytest.raises(ValueError, match="未设置 system_prompt_path"):
            spec._load_system_prompt()

    def test_raises_file_not_found_for_missing_file(self):
        """指定的 Prompt 文件不存在时抛出 FileNotFoundError。"""
        class MissingFileSpec(LLMAgentSpec):
            system_prompt_path = "nonexistent_prompt_v99.md"

        spec = MissingFileSpec()
        with patch("agent.skills.base.settings", Settings(prompts_root="/nonexistent/root")):
            with pytest.raises(FileNotFoundError):
                spec._load_system_prompt()
