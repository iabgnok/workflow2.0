"""技能基类单元测试。

覆盖：
- Skill[InputT, OutputT] 类变量声明与读取
- schema_summary() 内容生成（含输入/输出字段）
- LLMAgentSpec：_load_system_prompt() 加载与缓存（已由 test_llm_agent_spec.py 覆盖）
- IOSkillSpec / FlowSkillSpec 继承关系
- IdempotencyLevel 枚举值
- RetryPolicy 默认值
"""
import pytest
from pydantic import BaseModel, Field

from agent.skills.base import (
    FlowSkillSpec,
    IdempotencyLevel,
    IOSkillSpec,
    LLMAgentSpec,
    RetryPolicy,
    Skill,
)


# ── 测试辅助类型 ──────────────────────────────────────────────────────────

class DummyInput(BaseModel):
    file_path: str = Field(description="文件路径")
    encoding: str = Field(default="utf-8", description="文件编码")


class DummyOutput(BaseModel):
    content: str = Field(description="文件内容")


class DummySkill(Skill[DummyInput, DummyOutput]):
    name = "dummy_skill"
    description = "测试用技能"
    when_to_use = "单元测试时"
    do_not_use_when = "生产环境"
    idempotency = IdempotencyLevel.L0
    input_type = DummyInput
    output_type = DummyOutput


class MinimalSkill(Skill):
    name = "minimal"


class DummyIOSkill(IOSkillSpec):
    name = "dummy_io"


class DummyFlowSkill(FlowSkillSpec):
    name = "dummy_flow"


class DummyLLMSkill(LLMAgentSpec):
    name = "dummy_llm"
    system_prompt_path = "generator_system_v1.md"


# ── 类变量读取 ────────────────────────────────────────────────────────────

class TestSkillClassVars:
    def test_name_is_readable(self):
        assert DummySkill.name == "dummy_skill"

    def test_description_is_readable(self):
        assert DummySkill.description == "测试用技能"

    def test_idempotency_level(self):
        assert DummySkill.idempotency == IdempotencyLevel.L0

    def test_input_type_is_set(self):
        assert DummySkill.input_type is DummyInput

    def test_output_type_is_set(self):
        assert DummySkill.output_type is DummyOutput

    def test_default_retry_policy(self):
        assert isinstance(Skill.retry_policy, RetryPolicy)
        assert Skill.retry_policy.max_attempts == 3

    def test_unset_fields_default_to_empty_string(self):
        assert MinimalSkill.description == ""
        assert MinimalSkill.when_to_use == ""


# ── schema_summary() ──────────────────────────────────────────────────────

class TestSchemaSummary:
    def test_contains_skill_name(self):
        summary = DummySkill.schema_summary()
        assert "dummy_skill" in summary

    def test_contains_description(self):
        summary = DummySkill.schema_summary()
        assert "测试用技能" in summary

    def test_contains_input_field_names(self):
        summary = DummySkill.schema_summary()
        assert "file_path" in summary
        assert "encoding" in summary

    def test_contains_output_field_names(self):
        summary = DummySkill.schema_summary()
        assert "content" in summary

    def test_contains_idempotency(self):
        summary = DummySkill.schema_summary()
        assert "L0" in summary

    def test_when_to_use_included(self):
        summary = DummySkill.schema_summary()
        assert "单元测试时" in summary

    def test_do_not_use_when_included(self):
        summary = DummySkill.schema_summary()
        assert "生产环境" in summary

    def test_no_input_type_excludes_input_section(self):
        summary = MinimalSkill.schema_summary()
        assert "输入字段" not in summary

    def test_no_output_type_excludes_output_section(self):
        summary = MinimalSkill.schema_summary()
        assert "输出字段" not in summary


# ── 继承关系 ──────────────────────────────────────────────────────────────

class TestInheritance:
    def test_io_skill_is_skill_subclass(self):
        assert issubclass(IOSkillSpec, Skill)

    def test_flow_skill_is_skill_subclass(self):
        assert issubclass(FlowSkillSpec, Skill)

    def test_llm_agent_spec_is_skill_subclass(self):
        assert issubclass(LLMAgentSpec, Skill)

    def test_dummy_io_skill_instance(self):
        skill = DummyIOSkill()
        assert isinstance(skill, IOSkillSpec)
        assert isinstance(skill, Skill)

    def test_dummy_flow_skill_instance(self):
        skill = DummyFlowSkill()
        assert isinstance(skill, FlowSkillSpec)
        assert isinstance(skill, Skill)


# ── execute_step 默认抛出 ─────────────────────────────────────────────────

class TestExecuteStepNotImplemented:
    @pytest.mark.asyncio
    async def test_base_skill_raises_not_implemented(self):
        skill = MinimalSkill()
        with pytest.raises(NotImplementedError):
            await skill.execute_step({}, {})


# ── IdempotencyLevel 枚举 ─────────────────────────────────────────────────

class TestIdempotencyLevel:
    def test_l0_value(self):
        assert IdempotencyLevel.L0.value == "L0"

    def test_l1_value(self):
        assert IdempotencyLevel.L1.value == "L1"

    def test_l2_value(self):
        assert IdempotencyLevel.L2.value == "L2"

    def test_is_string_enum(self):
        assert isinstance(IdempotencyLevel.L0, str)


# ── RetryPolicy ──────────────────────────────────────────────────────────

class TestRetryPolicy:
    def test_default_max_attempts(self):
        p = RetryPolicy()
        assert p.max_attempts == 3

    def test_default_backoff(self):
        p = RetryPolicy()
        assert p.backoff_seconds == 1.0

    def test_custom_values(self):
        p = RetryPolicy(max_attempts=5, backoff_seconds=2.0, enabled=False)
        assert p.max_attempts == 5
        assert not p.enabled
