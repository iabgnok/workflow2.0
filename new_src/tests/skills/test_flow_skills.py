"""Flow 技能单元测试。

覆盖：
- SubWorkflowCall：metadata 声明、缺少 workflow 路径抛出、输入变量校验、正常执行
- VariableMapper：map_inputs required_keys 校验
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent.infra.variable_mapper import VariableMappingError, VariableMapper
from agent.skills.flow.sub_workflow_call import SubWorkflowCall


# ── SubWorkflowCall 元数据 ────────────────────────────────────────────────

class TestSubWorkflowCallMetadata:
    def test_name(self):
        assert SubWorkflowCall.name == "sub_workflow_call"

    def test_no_engine_import(self):
        """SubWorkflowCall 模块不应从 agent.engine 导入 VariableMapper。"""
        import agent.skills.flow.sub_workflow_call as mod
        import inspect
        src = inspect.getsource(mod)
        # 允许 engine.runner（本地导入），但 VariableMapper 必须来自 infra
        assert "from agent.infra.variable_mapper" in src
        assert "from agent.engine.variable_mapper" not in src


# ── 缺少 workflow 路径 ────────────────────────────────────────────────────

class TestSubWorkflowCallMissingWorkflow:
    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_workflow(self):
        skill = SubWorkflowCall()
        with pytest.raises(ValueError, match="缺少必须参数 'workflow'"):
            await skill.execute_step({"inputs": {}, "outputs": {}}, {})


# ── 输入变量校验 ──────────────────────────────────────────────────────────

class TestSubWorkflowCallInputValidation:
    @pytest.mark.asyncio
    async def test_raises_when_required_input_missing(self):
        """父 context 中缺少必须输入变量时，抛出 VariableMappingError。"""
        skill = SubWorkflowCall()
        step = {
            "workflow": "some_workflow.step.md",
            "inputs": {"blueprint": "blueprint"},  # blueprint 不在 context 中
            "outputs": {},
        }
        context = {}  # 缺少 blueprint
        with pytest.raises(VariableMappingError, match="blueprint"):
            await skill.execute_step(step, context)


# ── 正常执行 ──────────────────────────────────────────────────────────────

class TestSubWorkflowCallNormalExecution:
    @pytest.mark.asyncio
    async def test_calls_runner_with_mapped_context(self):
        """验证子 Runner 被正确创建，并以映射后的 context 初始化。"""
        skill = SubWorkflowCall()
        step = {
            "workflow": "sub.step.md",
            "inputs": {"req": "user_req"},
            "outputs": {"result": "output"},
        }
        parent_context = {"user_req": "用户需求文本"}

        mock_result = {
            "status": "success",
            "context": {"output": "子流程结果"},
            "run_id": "test-run-1",
        }
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(return_value=mock_result)

        with patch(
            "agent.engine.runner.Runner",
            return_value=mock_runner,
        ):
            result = await skill.execute_step(step, parent_context)

        assert result["__sub_workflow_status__"] == "success"
        assert result["result"] == "子流程结果"

    @pytest.mark.asyncio
    async def test_raises_on_sub_workflow_failure(self):
        """子工作流执行失败时抛出 RuntimeError。"""
        skill = SubWorkflowCall()
        step = {
            "workflow": "fail.step.md",
            "inputs": {"req": "req"},
            "outputs": {},
        }
        context = {"req": "value"}
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(return_value={"status": "failed"})

        with patch("agent.engine.runner.Runner", return_value=mock_runner):
            with pytest.raises(RuntimeError, match="子工作流执行失败"):
                await skill.execute_step(step, context)


# ── VariableMapper.map_inputs required_keys ──────────────────────────────

class TestVariableMapperRequiredKeys:
    def test_raises_when_required_key_missing(self):
        with pytest.raises(VariableMappingError, match="blueprint"):
            VariableMapper.map_inputs(
                {"other": "value"},
                {"blueprint": "blueprint"},
                required_keys=["blueprint"],
            )

    def test_no_error_when_required_key_present(self):
        result = VariableMapper.map_inputs(
            {"blueprint": "蓝图内容"},
            {"blueprint": "blueprint"},
            required_keys=["blueprint"],
        )
        assert result["blueprint"] == "蓝图内容"

    def test_no_required_keys_allows_missing_values(self):
        result = VariableMapper.map_inputs(
            {},
            {"blueprint": "blueprint"},
        )
        # 无 required_keys 时，缺失变量只 warning，不抛出
        assert "blueprint" not in result
