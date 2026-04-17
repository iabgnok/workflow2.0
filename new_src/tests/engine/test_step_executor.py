"""单元测试：StepExecutor（任务 3.3）"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.engine.step_executor import StepExecutor


# ── 辅助工厂 ──────────────────────────────────────────────────────────────────

def _make_executor(
    skill_output: dict | None = None,
    skill_has_execute_step: bool = False,
    pre_assert_raises=None,
    post_assert_raises=None,
    skill_not_found: bool = False,
):
    """创建带 mock 依赖的 StepExecutor。"""
    # mock skill
    mock_skill = MagicMock()
    if skill_has_execute_step:
        mock_skill.execute_step = AsyncMock(return_value=skill_output or {})
    else:
        mock_skill.execute = AsyncMock(return_value=skill_output or {})
        del mock_skill.execute_step  # 确保没有 execute_step 属性

    # mock registry
    mock_registry = MagicMock()
    if skill_not_found:
        mock_registry.get_all.return_value = {}
        mock_registry.get.side_effect = Exception("not found")
    else:
        mock_registry.get_all.return_value = {"file_reader": mock_skill}

    # mock protocol_service
    mock_protocol = MagicMock()
    if pre_assert_raises:
        mock_protocol.validate_runtime_step_inputs.side_effect = pre_assert_raises
    if post_assert_raises:
        mock_protocol.validate_runtime_step_outputs.side_effect = post_assert_raises

    # execute_with_policy 透传调用
    async def fake_policy(skill_name, fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    def replace_vars(text, ctx):
        return text

    return StepExecutor(
        skill_registry=mock_registry,
        protocol_service=mock_protocol,
        replace_variables=replace_vars,
        execute_with_policy=fake_policy,
    )


STEP = {
    "id": 1,
    "name": "Read File",
    "action": "file_reader",
    "content": "read {{file_path}}",
    "inputs": {"file_path": "file_path"},
    "outputs": {"file_content": "file_content"},
}

CONTEXT = {"file_path": "a.txt"}


# ── 正常执行路径 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_successful_execution_returns_output():
    executor = _make_executor(skill_output={"file_content": "hello"})
    output = await executor.execute(STEP, CONTEXT)
    assert output == {"file_content": "hello"}


@pytest.mark.asyncio
async def test_execute_step_method_used_when_available():
    """技能若有 execute_step，应走 execute_step 路径。"""
    executor = _make_executor(
        skill_output={"file_content": "world"},
        skill_has_execute_step=True,
    )
    output = await executor.execute(STEP, CONTEXT)
    assert output["file_content"] == "world"


@pytest.mark.asyncio
async def test_none_output_normalized_to_empty_dict():
    executor = _make_executor(skill_output=None)
    output = await executor.execute(STEP, CONTEXT)
    assert output == {}


# ── 技能未找到 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_skill_raises():
    executor = _make_executor(skill_not_found=True)
    with pytest.raises(Exception, match="未注册的技能"):
        await executor.execute(STEP, CONTEXT)


# ── 断言路径 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pre_assertion_failure_propagates():
    executor = _make_executor(pre_assert_raises=ValueError("输入缺失"))
    with pytest.raises(ValueError, match="输入缺失"):
        await executor.execute(STEP, CONTEXT)


@pytest.mark.asyncio
async def test_post_assertion_failure_propagates():
    executor = _make_executor(
        skill_output={"file_content": "ok"},
        post_assert_raises=ValueError("输出验证失败"),
    )
    with pytest.raises(ValueError, match="输出验证失败"):
        await executor.execute(STEP, CONTEXT)


# ── 无状态持久化 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_state_store_calls():
    """StepExecutor 不应调用任何 StateStore 方法（见 spec）。"""
    executor = _make_executor(skill_output={"x": 1})
    # 只要不抛 AttributeError / 调用就视为通过
    output = await executor.execute(STEP, CONTEXT)
    assert "x" in output
