"""LLM 技能单元测试。

覆盖：
- Generator：metadata 声明、_to_workflow_model 转换、_validate_actions 校验
- Evaluator：metadata 声明、空 artifact 快速失败、静态扫描命中直接 REJECTED
- Planner：metadata 声明（execute_step 需真实 LLM，此处不测）
- LLMPromptCall：metadata 声明、缺少 prompt 块返回 {}
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.engine.protocol.models import WorkflowModel
from agent.skills.base import IdempotencyLevel
from agent.skills.llm.generator import LLMGeneratorCall
from agent.skills.llm.evaluator import LLMEvaluatorCall
from agent.skills.llm.planner import LLMPlannerCall
from agent.skills.llm.prompt import LLMPromptCall
from agent.skills.llm.types import StructuredWorkflowArtifact, WorkflowStepSpec


# ── Generator ─────────────────────────────────────────────────────────────

class TestGeneratorMetadata:
    def test_name(self):
        assert LLMGeneratorCall.name == "llm_generator_call"

    def test_idempotency(self):
        assert LLMGeneratorCall.idempotency == IdempotencyLevel.L2

    def test_system_prompt_path(self):
        assert LLMGeneratorCall.system_prompt_path == "generator_system_v1.md"


class TestGeneratorToWorkflowModel:
    def _make_artifact(self) -> StructuredWorkflowArtifact:
        return StructuredWorkflowArtifact(
            workflow_name="Test_Workflow",
            description="测试工作流",
            inputs=["user_input"],
            outputs=["result"],
            steps=[
                WorkflowStepSpec(
                    name="读取文件",
                    action="file_reader",
                    inputs=["file_path"],
                    outputs=["file_content"],
                )
            ],
            explanation="测试",
        )

    def test_converts_workflow_name(self):
        artifact = self._make_artifact()
        model = LLMGeneratorCall._to_workflow_model(artifact)
        assert model.metadata.name == "Test_Workflow"

    def test_converts_description(self):
        artifact = self._make_artifact()
        model = LLMGeneratorCall._to_workflow_model(artifact)
        assert model.metadata.description == "测试工作流"

    def test_converts_steps(self):
        artifact = self._make_artifact()
        model = LLMGeneratorCall._to_workflow_model(artifact)
        assert len(model.steps) == 1
        assert model.steps[0].action == "file_reader"
        assert model.steps[0].name == "读取文件"

    def test_step_id_is_one_based(self):
        artifact = self._make_artifact()
        model = LLMGeneratorCall._to_workflow_model(artifact)
        assert model.steps[0].id == 1

    def test_step_inputs_are_identity_mapping(self):
        artifact = self._make_artifact()
        model = LLMGeneratorCall._to_workflow_model(artifact)
        assert model.steps[0].inputs == {"file_path": "file_path"}

    def test_returns_workflow_model_instance(self):
        artifact = self._make_artifact()
        model = LLMGeneratorCall._to_workflow_model(artifact)
        assert isinstance(model, WorkflowModel)

    def test_step_content_contains_action_and_io_tokens(self):
        artifact = self._make_artifact()
        model = LLMGeneratorCall._to_workflow_model(artifact)
        content = model.steps[0].content
        assert "file_reader" in content
        assert "file_path" in content
        assert "file_content" in content

    def test_deduplicates_inputs(self):
        artifact = StructuredWorkflowArtifact(
            workflow_name="W",
            description="",
            inputs=["a", "a", "b"],
            outputs=[],
            steps=[],
            explanation="",
        )
        model = LLMGeneratorCall._to_workflow_model(artifact)
        assert model.metadata.inputs == ["a", "b"]


class TestGeneratorValidateActions:
    def test_raises_on_unknown_action(self):
        gen = LLMGeneratorCall.__new__(LLMGeneratorCall)
        artifact = StructuredWorkflowArtifact(
            workflow_name="W",
            description="",
            inputs=[],
            outputs=[],
            steps=[WorkflowStepSpec(name="S", action="nonexistent_skill")],
            explanation="",
        )
        with pytest.raises(ValueError, match="WF_UNKNOWN_ACTIONS"):
            gen._validate_actions(artifact, ["file_reader"])

    def test_no_error_when_skills_empty(self):
        gen = LLMGeneratorCall.__new__(LLMGeneratorCall)
        artifact = StructuredWorkflowArtifact(
            workflow_name="W", description="", inputs=[], outputs=[],
            steps=[WorkflowStepSpec(name="S", action="anything")], explanation=""
        )
        gen._validate_actions(artifact, [])  # should not raise


class TestGeneratorNormalizeActions:
    def test_fuzzy_match_action_to_registered_skill(self):
        gen = LLMGeneratorCall.__new__(LLMGeneratorCall)
        artifact = StructuredWorkflowArtifact(
            workflow_name="W",
            description="",
            inputs=[],
            outputs=[],
            steps=[WorkflowStepSpec(name="S", action="file_readr")],
            explanation="",
        )
        audits, defects = gen._normalize_actions(artifact, ["file_reader"], [])
        assert defects == []
        assert artifact.steps[0].action == "file_reader"
        assert audits[0]["reason"] in {"fuzzy_match", "mapped_from_blueprint_action_type"}

    def test_unknown_action_returns_model_fixable_defect(self):
        gen = LLMGeneratorCall.__new__(LLMGeneratorCall)
        artifact = StructuredWorkflowArtifact(
            workflow_name="W",
            description="",
            inputs=[],
            outputs=[],
            steps=[WorkflowStepSpec(name="S", action="totally_unknown")],
            explanation="",
        )
        audits, defects = gen._normalize_actions(artifact, ["file_reader"], [])
        assert audits == []
        assert len(defects) == 1
        assert defects[0]["fix_category"] == "model-fixable"


class TestGeneratorExecuteStep:
    @pytest.mark.asyncio
    async def test_raises_when_llm_not_initialized(self):
        gen = LLMGeneratorCall.__new__(LLMGeneratorCall)
        gen._prompt_cache = {}
        gen._structured_llm = None
        with pytest.raises(ValueError, match="未成功初始化"):
            await gen.execute_step({}, {})

    @pytest.mark.asyncio
    async def test_returns_workflow_model_in_output(self):
        gen = LLMGeneratorCall.__new__(LLMGeneratorCall)
        gen._prompt_cache = {}
        from agent.engine.protocol.service import ProtocolService
        gen._protocol_service = ProtocolService()
        artifact = StructuredWorkflowArtifact(
            workflow_name="Test",
            description="",
            inputs=[],
            outputs=[],
            steps=[WorkflowStepSpec(name="S", action="file_reader")],
            explanation="OK",
        )
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=artifact)
        gen._structured_llm = mock_llm
        with patch.object(gen, "_load_system_prompt", return_value=""):
            result = await gen.execute_step({}, {"registered_skills": ["file_reader"]})
        assert isinstance(result["final_artifact"], WorkflowModel)

    @pytest.mark.asyncio
    async def test_precheck_failure_then_retry_succeeds(self):
        gen = LLMGeneratorCall.__new__(LLMGeneratorCall)
        gen._prompt_cache = {}
        from agent.engine.protocol.service import ProtocolService
        gen._protocol_service = ProtocolService()

        bad_artifact = StructuredWorkflowArtifact(
            workflow_name="Test",
            description="",
            inputs=[],
            outputs=[],
            steps=[WorkflowStepSpec(name="S", action="unknown_skill_name")],
            explanation="bad",
        )
        good_artifact = StructuredWorkflowArtifact(
            workflow_name="Test",
            description="",
            inputs=[],
            outputs=[],
            steps=[WorkflowStepSpec(name="S", action="file_reader")],
            explanation="good",
        )
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=[bad_artifact, good_artifact])
        gen._structured_llm = mock_llm

        with patch.object(gen, "_load_system_prompt", return_value=""):
            result = await gen.execute_step(
                {},
                {
                    "registered_skills": ["file_reader"],
                    "structured_validation_max_retries": 1,
                },
            )

        assert isinstance(result["final_artifact"], WorkflowModel)
        assert result["generator_validation_retry_count"] == 1


# ── Evaluator ─────────────────────────────────────────────────────────────

class TestEvaluatorMetadata:
    def test_name(self):
        assert LLMEvaluatorCall.name == "llm_evaluator_call"

    def test_idempotency(self):
        assert LLMEvaluatorCall.idempotency == IdempotencyLevel.L0


class TestEvaluatorEmptyArtifact:
    @pytest.mark.asyncio
    async def test_empty_string_returns_rejected(self):
        ev = LLMEvaluatorCall.__new__(LLMEvaluatorCall)
        ev._prompt_cache = {}
        ev._structured_llm = MagicMock()
        result = await ev._run("", escalation_level=1)
        assert result["evaluator_report"]["status"] == "REJECTED"

    @pytest.mark.asyncio
    async def test_none_returns_rejected(self):
        ev = LLMEvaluatorCall.__new__(LLMEvaluatorCall)
        ev._prompt_cache = {}
        ev._structured_llm = MagicMock()
        result = await ev._run(None, escalation_level=1)
        assert result["evaluator_report"]["status"] == "REJECTED"


class TestEvaluatorStaticScan:
    @pytest.mark.asyncio
    async def test_danger_keyword_causes_rejection_without_llm(self):
        """静态扫描命中安全违规时，不调用 LLM 直接 REJECTED。"""
        from agent.engine.protocol.models import WorkflowMetadata, WorkflowStep

        model = WorkflowModel(
            metadata=WorkflowMetadata(name="W"),
            steps=[
                WorkflowStep(
                    id=1,
                    name="危险操作",
                    action="llm_prompt_call",
                    content="rm -rf /tmp",  # 命中 DANGER_KEYWORDS
                )
            ],
        )
        ev = LLMEvaluatorCall.__new__(LLMEvaluatorCall)
        ev._prompt_cache = {}
        ev._structured_llm = AsyncMock()  # 不应被调用
        result = await ev._run(model, escalation_level=1)
        assert result["evaluator_report"]["status"] == "REJECTED"
        ev._structured_llm.ainvoke.assert_not_called()


class TestEvaluatorPrecheckShortCircuit:
    @pytest.mark.asyncio
    async def test_precheck_defects_skip_llm_semantic_review(self):
        ev = LLMEvaluatorCall.__new__(LLMEvaluatorCall)
        ev._prompt_cache = {}
        ev._structured_llm = AsyncMock()
        result = await ev.execute_step(
            {},
            {
                "final_artifact": "ignored",
                "pre_evaluator_defects": [
                    {
                        "location": "step:1",
                        "type": "PROTOCOL_ERROR",
                        "reason": "bad action",
                        "suggestion": "fix action",
                    }
                ],
            },
        )
        assert result["evaluator_report"]["status"] == "REJECTED"
        ev._structured_llm.ainvoke.assert_not_called()


# ── Planner ───────────────────────────────────────────────────────────────

class TestPlannerMetadata:
    def test_name(self):
        assert LLMPlannerCall.name == "llm_planner_call"

    def test_idempotency(self):
        assert LLMPlannerCall.idempotency == IdempotencyLevel.L2

    def test_system_prompt_path(self):
        assert LLMPlannerCall.system_prompt_path == "planner_system_v1.md"


class TestPlannerExecuteStep:
    @pytest.mark.asyncio
    async def test_returns_dict_not_json_string(self):
        """核心契约：workflow_blueprint 必须是 dict，不是 JSON 字符串。"""
        from agent.skills.llm.planner import WorkflowBlueprint

        planner = LLMPlannerCall.__new__(LLMPlannerCall)
        planner._prompt_cache = {}
        blueprint = WorkflowBlueprint(
            workflow_name="Test",
            description="测试",
            estimated_steps=2,
            should_split=False,
            inputs=["req"],
            outputs=["res"],
            handoff_contracts="无",
            main_flow_steps=[],
        )
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=blueprint)
        planner._structured_llm = mock_llm
        with patch.object(planner, "_load_system_prompt", return_value=""):
            result = await planner.execute_step({}, {"requirement": "生成测试工作流"})
        assert isinstance(result["workflow_blueprint"], dict)
        assert result["workflow_blueprint"]["workflow_name"] == "Test"


# ── LLMPromptCall ─────────────────────────────────────────────────────────

class TestPromptCallMetadata:
    def test_name(self):
        assert LLMPromptCall.name == "llm_prompt_call"

    def test_idempotency(self):
        assert LLMPromptCall.idempotency == IdempotencyLevel.L2


class TestPromptCallExecuteStep:
    @pytest.mark.asyncio
    async def test_no_prompt_block_returns_empty(self):
        skill = LLMPromptCall.__new__(LLMPromptCall)
        skill._prompt_cache = {}
        skill._client = AsyncMock()
        result = await skill.execute_step({"content": "无代码块"}, {})
        assert result == {}
        skill._client.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_extracts_prompt_block_and_calls_llm(self):
        skill = LLMPromptCall.__new__(LLMPromptCall)
        skill._prompt_cache = {}
        mock_response = MagicMock()
        mock_response.content = "LLM 输出"
        skill._client = MagicMock()
        skill._client.ainvoke = AsyncMock(return_value=mock_response)
        content = "```prompt\n你好世界\n```"
        result = await skill.execute_step({"content": content}, {})
        assert result["llm_output"] == "LLM 输出"
        skill._client.ainvoke.assert_awaited_once_with("你好世界")


# ── StructuredWorkflowArtifact.action 校验 ────────────────────────────────

class TestStructuredWorkflowArtifact:
    def test_empty_action_raises(self):
        with pytest.raises(Exception):
            WorkflowStepSpec(name="S", action="")

    def test_whitespace_action_raises(self):
        with pytest.raises(Exception):
            WorkflowStepSpec(name="S", action="   ")

    def test_valid_action_strips_whitespace(self):
        spec = WorkflowStepSpec(name="S", action="  file_reader  ")
        assert spec.action == "file_reader"
