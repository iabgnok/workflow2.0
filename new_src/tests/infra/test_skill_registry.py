"""SkillRegistry 递归扫描和 manifest 生成测试。"""
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from agent.infra.skill_registry import SkillNotFoundError, SkillRegistry


# ── 辅助工具 ──────────────────────────────────────────────────────────────────

def _make_skill_module(module_name: str, skill_name: str, description: str = "") -> ModuleType:
    """创建一个内存中的伪技能模块，包含一个有 execute_step 方法的技能类。"""
    mod = ModuleType(module_name)
    mod.__name__ = module_name

    # 在类体外捕获局部变量（Python 类体不继承外层函数的局部作用域）
    _name = skill_name
    _desc = description
    _when = f"当需要 {skill_name} 时"

    class FakeSkill:
        name = _name
        description = _desc
        when_to_use = _when
        do_not_use_when = ""

        def schema_summary(self):
            lines = [f"=== {self.name} ==="]
            if self.description:
                lines.append(f"描述: {self.description}")
            if self.when_to_use:
                lines.append(f"使用场景: {self.when_to_use}")
            return "\n".join(lines)

        async def execute_step(self, step, context):
            return {}

    FakeSkill.__module__ = module_name
    mod.FakeSkill = FakeSkill
    return mod


# ── SkillNotFoundError 测试 ────────────────────────────────────────────────────

class TestSkillNotFoundError:
    def test_is_exception(self):
        assert issubclass(SkillNotFoundError, Exception)

    def test_raises_with_message(self):
        with pytest.raises(SkillNotFoundError, match="技能 'missing' 未注册"):
            registry = SkillRegistry()
            registry.get("missing")


# ── 手动注册测试 ───────────────────────────────────────────────────────────────

class TestManualRegistration:
    def test_register_and_get(self):
        registry = SkillRegistry()
        skill = MagicMock()
        registry.register("my_skill", skill)
        assert registry.get("my_skill") is skill

    def test_contains_true(self):
        registry = SkillRegistry()
        registry.register("s1", MagicMock())
        assert registry.contains("s1") is True

    def test_contains_false(self):
        registry = SkillRegistry()
        assert registry.contains("nonexistent") is False

    def test_get_names_sorted(self):
        registry = SkillRegistry()
        registry.register("b_skill", MagicMock())
        registry.register("a_skill", MagicMock())
        registry.register("c_skill", MagicMock())
        assert registry.get_names() == ["a_skill", "b_skill", "c_skill"]

    def test_get_all(self):
        registry = SkillRegistry()
        s1 = MagicMock()
        s2 = MagicMock()
        registry.register("skill1", s1)
        registry.register("skill2", s2)
        all_skills = registry.get_all()
        assert all_skills == {"skill1": s1, "skill2": s2}


# ── 递归扫描测试 ───────────────────────────────────────────────────────────────

class TestScan:
    def test_scan_nonexistent_directory_does_not_raise(self, tmp_path):
        registry = SkillRegistry()
        registry.scan(str(tmp_path / "nonexistent"))
        assert registry.get_names() == []

    def test_scan_discovers_skills_in_subdirs(self, tmp_path):
        """扫描应在 llm/、io/、flow/ 子目录中发现技能。"""
        # 创建三个子目录的 py 文件
        (tmp_path / "llm").mkdir()
        (tmp_path / "io").mkdir()
        (tmp_path / "flow").mkdir()
        (tmp_path / "llm" / "my_llm_skill.py").write_text("")
        (tmp_path / "io" / "my_io_skill.py").write_text("")
        (tmp_path / "flow" / "my_flow_skill.py").write_text("")

        llm_mod = _make_skill_module("agent.skills.llm.my_llm_skill", "my_llm_skill", "LLM 技能")
        io_mod = _make_skill_module("agent.skills.io.my_io_skill", "my_io_skill", "IO 技能")
        flow_mod = _make_skill_module("agent.skills.flow.my_flow_skill", "my_flow_skill", "Flow 技能")

        import_map = {
            "agent.skills.llm.my_llm_skill": llm_mod,
            "agent.skills.io.my_io_skill": io_mod,
            "agent.skills.flow.my_flow_skill": flow_mod,
        }

        with patch("agent.infra.skill_registry.importlib.import_module", side_effect=lambda n: import_map[n]):
            registry = SkillRegistry()
            registry.scan(str(tmp_path))

        assert registry.contains("my_llm_skill")
        assert registry.contains("my_io_skill")
        assert registry.contains("my_flow_skill")

    def test_scan_skips_private_files(self, tmp_path):
        """以 _ 开头的文件（__init__.py、_helper.py 等）应被跳过。"""
        (tmp_path / "llm").mkdir()
        (tmp_path / "llm" / "__init__.py").write_text("")
        (tmp_path / "llm" / "_internal.py").write_text("")
        (tmp_path / "llm" / "real_skill.py").write_text("")

        real_mod = _make_skill_module("agent.skills.llm.real_skill", "real_skill")

        with patch(
            "agent.infra.skill_registry.importlib.import_module",
            return_value=real_mod,
        ):
            registry = SkillRegistry()
            registry.scan(str(tmp_path))

        assert registry.contains("real_skill")
        # 私有文件不应触发 import
        names = registry.get_names()
        assert "__init__" not in names
        assert "_internal" not in names

    def test_scan_handles_import_error_gracefully(self, tmp_path):
        """模块加载失败时，应记录警告并继续扫描，不抛出异常。"""
        (tmp_path / "llm").mkdir()
        (tmp_path / "llm" / "bad_skill.py").write_text("")

        with patch(
            "agent.infra.skill_registry.importlib.import_module",
            side_effect=ImportError("missing dep"),
        ):
            registry = SkillRegistry()
            registry.scan(str(tmp_path))  # 不应抛出异常

        assert registry.get_names() == []

    def test_scan_skill_in_subdirectory_registered_by_name_attribute(self, tmp_path):
        """技能应以 class.name 属性为注册键，而非文件名。"""
        (tmp_path / "llm").mkdir()
        (tmp_path / "llm" / "generator.py").write_text("")

        mod = _make_skill_module("agent.skills.llm.generator", "llm_generator_call")
        with patch("agent.infra.skill_registry.importlib.import_module", return_value=mod):
            registry = SkillRegistry()
            registry.scan(str(tmp_path))

        assert registry.contains("llm_generator_call")
        assert not registry.contains("generator")


# ── build_skill_manifest 测试 ─────────────────────────────────────────────────

class TestBuildSkillManifest:
    def test_empty_registry_returns_placeholder(self):
        registry = SkillRegistry()
        manifest = registry.build_skill_manifest()
        assert "没有" in manifest or "（" in manifest

    def test_manifest_contains_all_skills(self):
        """7 个技能全部注册后，manifest 应包含全部技能的信息。"""
        registry = SkillRegistry()
        skill_names = [f"skill_{i}" for i in range(7)]
        for name in skill_names:
            mod = _make_skill_module(f"agent.skills.llm.{name}", name, f"{name} 的描述")
            instance = mod.FakeSkill()
            registry.register(name, instance)

        manifest = registry.build_skill_manifest()
        for name in skill_names:
            assert name in manifest

    def test_manifest_uses_schema_summary_if_available(self):
        """若技能实现了 schema_summary()，应使用其返回值构建 manifest。"""
        skill = MagicMock()
        skill.schema_summary.return_value = "=== custom_skill ===\n描述: 自定义技能"
        skill.name = "custom_skill"

        registry = SkillRegistry()
        registry.register("custom_skill", skill)
        manifest = registry.build_skill_manifest()
        assert "=== custom_skill ===" in manifest
        assert "自定义技能" in manifest

    def test_manifest_fallback_when_no_schema_summary(self):
        """若技能没有 schema_summary()，应回退为简单描述。"""
        skill = MagicMock(spec=[])  # spec=[] 确保没有任何属性
        skill.name = "plain_skill"
        # 手动绑定缺少的 description
        skill.description = "简单描述"

        registry = SkillRegistry()
        registry.register("plain_skill", skill)
        manifest = registry.build_skill_manifest()
        assert "plain_skill" in manifest

    def test_manifest_skills_sorted_by_name(self):
        """manifest 中的技能应按名称字母序排列。"""
        registry = SkillRegistry()
        for name in ["z_skill", "a_skill", "m_skill"]:
            skill = MagicMock()
            skill.schema_summary.return_value = f"=== {name} ==="
            registry.register(name, skill)

        manifest = registry.build_skill_manifest()
        pos_a = manifest.index("a_skill")
        pos_m = manifest.index("m_skill")
        pos_z = manifest.index("z_skill")
        assert pos_a < pos_m < pos_z
