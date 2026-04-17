"""E2E 测试 Test 2：将生成的 WorkflowModel 通过 Runner 执行。

使用确定性的最简 WorkflowModel（2 步，Mock Skill），
验证 Runner 能正确驱动动态生成工作流的编排逻辑。

需要 .env 中配置 DEEPSEEK_API_KEY 才会运行（与 Test 1 保持一致）。
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest
from unittest.mock import AsyncMock, MagicMock
from tests.e2e.conftest import has_deepseek_api_key

# 将 new_src 加入 sys.path（兼容直接运行）
_new_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _new_src not in sys.path:
    sys.path.insert(0, _new_src)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not has_deepseek_api_key(),
        reason="DEEPSEEK_API_KEY not set",
    ),
]


# ── Fixture：最简 WorkflowModel（module-scope，不依赖 LLM） ──────────────────

@pytest.fixture(scope="module")
def workflow_model():
    """构造 2 步最简 WorkflowModel，action 分别为 mock_skill_a / mock_skill_b。"""
    from agent.engine.protocol.models import WorkflowModel, WorkflowMetadata, WorkflowStep

    model = WorkflowModel(
        metadata=WorkflowMetadata(
            name="test-generated-workflow",
            description="E2E 测试用最简工作流",
        ),
        steps=[
            WorkflowStep(
                id=1,
                name="Step A",
                action="mock_skill_a",
                outputs={"result_a": "result_a"},
            ),
            WorkflowStep(
                id=2,
                name="Step B",
                action="mock_skill_b",
                outputs={"result_b": "result_b"},
            ),
        ],
    )
    return model


# ── 工具函数：序列化 WorkflowModel 到临时文件 ──────────────────────────────────

def _serialize_workflow_to_tempfile(model) -> str:
    """将 WorkflowModel 序列化为 .step.md 格式，写入临时文件，返回路径。"""
    content = model.to_markdown()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".step.md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


# ── 辅助：构造带 Mock Skill 的 Runner（参照 test_runner_integration.py） ────────

def _make_mock_runner(filepath: str):
    """构造一个使用真实 ProtocolService + Mock Skill 的 Runner。"""
    from agent.engine.runner import Runner
    from agent.engine.execution_hooks import ExecutionHooks
    from agent.engine.execution_observer import ExecutionObserver
    from agent.engine.condition_evaluator import ConditionEvaluator
    from agent.engine.resume_strategy import ResumeStrategy
    from agent.engine.step_executor import StepExecutor
    from agent.engine.parser import WorkflowParser
    from agent.engine.protocol.service import ProtocolService

    # Mock StateStore
    ss = MagicMock()
    ss.connect = AsyncMock()
    ss.close = AsyncMock()
    ss.load_run_state = AsyncMock(return_value=None)
    ss.load_latest_step_state = AsyncMock(return_value=None)
    ss.save_run_state = AsyncMock()
    ss.save_step_state = AsyncMock()
    ss.save_run_meta = AsyncMock()

    # Mock Skill（两个，对应 mock_skill_a / mock_skill_b）
    mock_skill = MagicMock()
    del mock_skill.execute_step
    mock_skill.execute = AsyncMock(return_value={"result_a": "ok", "result_b": "ok"})

    registry = MagicMock()
    registry.get_all.return_value = {
        "mock_skill_a": mock_skill,
        "mock_skill_b": mock_skill,
    }

    # 真实 ProtocolService 解析临时文件
    protocol = ProtocolService()

    async def fake_policy(skill_name, fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    observer = MagicMock(spec=ExecutionObserver)
    observer.on_step_start = AsyncMock()
    observer.on_step_end = AsyncMock()
    observer.flush = AsyncMock()

    runner = Runner.__new__(Runner)
    runner.filepath = filepath
    runner.context = {}
    runner.state_store = ss
    runner._skill_registry = registry
    runner._protocol = protocol
    runner._hooks = ExecutionHooks()
    runner._observer = observer
    runner._evaluator = ConditionEvaluator()
    runner._resume = ResumeStrategy()
    runner._executor = StepExecutor(
        skill_registry=registry,
        protocol_service=protocol,
        replace_variables=WorkflowParser.replace_variables,
        execute_with_policy=fake_policy,
    )
    return runner


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2：Runner 执行生成的工作流
# ═══════════════════════════════════════════════════════════════════════════════

async def test_runner_executes_generated_workflow(workflow_model):
    """Test 2：将 WorkflowModel 序列化后，Runner 能正确执行并返回 success。"""
    tmpfile = _serialize_workflow_to_tempfile(workflow_model)
    try:
        runner = _make_mock_runner(tmpfile)
        result = await runner.run()
        assert result["status"] == "success", (
            f"Runner 执行失败，status={result.get('status')}"
        )
    finally:
        os.unlink(tmpfile)


async def test_serialization_roundtrip(workflow_model):
    """3.5：序列化往返一致性验证。

    parse(to_markdown(model)) 步骤数应与原始 WorkflowModel 一致。
    """
    from agent.engine.protocol.service import ProtocolService

    tmpfile = _serialize_workflow_to_tempfile(workflow_model)
    try:
        parsed_model, _ = ProtocolService().parse_workflow_file(tmpfile)
        assert len(parsed_model.steps) == len(workflow_model.steps), (
            f"序列化往返步骤数不一致：原始 {len(workflow_model.steps)}，"
            f"解析后 {len(parsed_model.steps)}"
        )
    finally:
        os.unlink(tmpfile)
