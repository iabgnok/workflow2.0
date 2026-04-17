"""集成测试：ChampionTracker + Runner 完整 Meta Workflow 循环。

通过 Mock 隔离外部依赖（StateStore、WorkflowRegistry、LLM 技能），
验证 ChampionTracker 钩子在 Runner 执行循环中的端到端行为。
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.engine.runner import Runner
from agent.engine.execution_observer import ExecutionObserver
from agent.engine.condition_evaluator import ConditionEvaluator
from agent.engine.resume_strategy import ResumeStrategy
from agent.engine.step_executor import StepExecutor
from agent.engine.parser import WorkflowParser
from agent.orchestration.champion_tracker import ChampionTracker


# ── 测试辅助工厂 ──────────────────────────────────────────────────────────────

def _make_step(step_id, action="dummy_skill", on_reject=None, condition=None):
    return {
        "id": step_id,
        "name": f"Step {step_id}",
        "action": action,
        "content": f"step {step_id} content",
        "condition": condition,
        "on_reject": on_reject,
        "inputs": {},
        "outputs": {"out": "out"},
    }


def _make_state_store():
    ss = MagicMock()
    ss.connect = AsyncMock()
    ss.close = AsyncMock()
    ss.load_run_state = AsyncMock(return_value=None)
    ss.load_latest_step_state = AsyncMock(return_value=None)
    ss.save_run_state = AsyncMock()
    ss.save_step_state = AsyncMock()
    ss.save_run_meta = AsyncMock()
    ss.load_run_meta = AsyncMock(return_value=None)
    ss.load_latest_champion_by_composite = AsyncMock(return_value=None)
    return ss


def _make_observer():
    obs = MagicMock(spec=ExecutionObserver)
    obs.on_step_start = AsyncMock()
    obs.on_step_end = AsyncMock()
    obs.flush = AsyncMock()
    return obs


def _make_runner_with_tracker(
    steps,
    skill_outputs: dict | None = None,
    state_store=None,
    tracker: ChampionTracker | None = None,
    initial_context: dict | None = None,
):
    """构造携带 ChampionTracker 的完整 Mock Runner。

    skill_outputs: {action_name: output_dict} 映射
    """
    ss = state_store or _make_state_store()

    # 构造每个技能的 Mock
    all_outputs = skill_outputs or {}

    def _make_skill_for(action: str):
        output = all_outputs.get(action, {})
        sk = MagicMock()
        del sk.execute_step
        sk.execute = AsyncMock(return_value=output)
        return sk

    skills = {a: _make_skill_for(a) for a in set(s["action"] for s in steps)}
    registry = MagicMock()
    registry.get_all.return_value = skills

    wf_model = MagicMock()
    wf_model.metadata.name = "Meta Main Workflow"
    protocol = MagicMock()
    protocol.parse_workflow_file.return_value = (wf_model, {"steps": steps})
    protocol.validate_runtime_step_inputs.return_value = None
    protocol.validate_runtime_step_outputs.return_value = None

    async def fake_policy(skill_name, fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    runner = Runner.__new__(Runner)
    runner.filepath = "meta.step.md"
    runner.context = dict(initial_context or {})
    runner.state_store = ss
    runner._skill_registry = registry
    runner._protocol = protocol
    runner._hooks = tracker or ChampionTracker(
        state_store=ss,
        workflow_registry=MagicMock(),
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )
    runner._observer = _make_observer()
    runner._evaluator = ConditionEvaluator()
    runner._resume = ResumeStrategy()
    runner._executor = StepExecutor(registry, protocol, WorkflowParser.replace_variables, fake_policy)
    return runner, ss


# ═══════════════════════════════════════════════════════════════════════════════
# 场景 1：全新运行，无 Champion，正常三步执行
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fresh_run_no_champion_all_steps_execute():
    """无 Champion 时，三步全部执行，evaluator_report APPROVED 后更新 champion。"""
    steps = [
        _make_step(1, action="planner"),
        _make_step(2, action="designer"),
        _make_step(3, action="evaluator"),
    ]
    ss = _make_state_store()
    ss.load_latest_champion_by_composite.return_value = None

    skill_outputs = {
        "planner": {"workflow_blueprint": json.dumps({"workflow_name": "WF", "main_flow_steps": []})},
        "designer": {"final_artifact": "# generated workflow"},
        "evaluator": {"evaluator_report": {"status": "APPROVED", "score": 88, "overall_feedback": "good"}},
    }

    tracker = ChampionTracker(
        state_store=ss,
        workflow_registry=MagicMock(),
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )
    runner, _ = _make_runner_with_tracker(steps, skill_outputs=skill_outputs, state_store=ss, tracker=tracker)

    # on_run_end 里的注册逻辑通过 patch 绕过
    with patch.object(tracker, "on_run_end", new_callable=AsyncMock):
        result = await runner.run()

    assert result["status"] == "approved_unverified"
    # evaluator_report 更新了 champion
    assert runner.context.get("champion_json") is not None
    assert runner.context["champion_json"]["score"] == 88


# ═══════════════════════════════════════════════════════════════════════════════
# 场景 2：有 Champion，复用时跳过 Designer 和 Evaluator
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reuse_champion_skips_designer_and_evaluator():
    """Champion 注水后，Step 2 和 Step 3 被跳过，只执行 Step 1（Planner）。"""
    steps = [
        _make_step(1, action="planner"),
        _make_step(2, action="designer"),
        _make_step(3, action="evaluator"),
    ]
    ss = _make_state_store()

    existing_champion = {
        "score": 92,
        "final_artifact": "# champion workflow",
        "evaluator_report": {"status": "APPROVED", "score": 92},
    }
    ss.load_latest_champion_by_composite.return_value = {"champion_json": existing_champion}

    skill_outputs = {
        "planner": {
            "requirement": "生成工作流",
            "workflow_blueprint": json.dumps({"workflow_name": "WF", "main_flow_steps": []}),
        },
        "designer": {"final_artifact": "# should not be called"},
        "evaluator": {"evaluator_report": {"status": "APPROVED", "score": 50}},
    }

    tracker = ChampionTracker(
        state_store=ss,
        workflow_registry=MagicMock(),
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )
    runner, _ = _make_runner_with_tracker(
        steps,
        skill_outputs=skill_outputs,
        state_store=ss,
        tracker=tracker,
        initial_context={
            "requirement": "生成工作流",
            "workflow_blueprint": json.dumps({"workflow_name": "WF", "main_flow_steps": []}),
        },
    )

    with patch.object(tracker, "on_run_end", new_callable=AsyncMock):
        result = await runner.run()

    assert result["status"] == "approved_unverified"
    # Designer(2) 和 Evaluator(3) 被跳过，step_state 只有 step 1
    saved_step_ids = [call.args[1] for call in runner.state_store.save_step_state.call_args_list]
    assert 1 in saved_step_ids
    assert 2 not in saved_step_ids
    assert 3 not in saved_step_ids
    # context 里的 final_artifact 应是 Champion 的
    assert runner.context.get("final_artifact") == "# champion workflow"


# ═══════════════════════════════════════════════════════════════════════════════
# 场景 3：on_run_start 设置 __reuse_champion__，on_step_before 正确响应
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_on_run_start_sets_reuse_flag():
    """on_run_start 找到复合指纹匹配时，context 中 __reuse_champion__ 为 True。"""
    ss = _make_state_store()
    existing_champion = {
        "score": 80,
        "final_artifact": "# wf",
        "evaluator_report": {"status": "APPROVED"},
    }
    ss.load_latest_champion_by_composite.return_value = {"champion_json": existing_champion}

    tracker = ChampionTracker(
        state_store=ss,
        workflow_registry=MagicMock(),
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )
    context = {
        "requirement": "测试需求",
        "workflow_blueprint": json.dumps({"workflow_name": "WF", "main_flow_steps": []}),
    }
    await tracker.on_run_start("run-42", context)
    assert context["__reuse_champion__"] is True
    assert context["final_artifact"] == "# wf"


# ═══════════════════════════════════════════════════════════════════════════════
# 场景 4：on_run_end 协议错误回流
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_on_run_end_protocol_errors_replace_prev_defects_with_latest_round():
    """注册预检失败时，仅保留本轮最新缺陷并写入摘要。"""
    ss = _make_state_store()
    tracker = ChampionTracker(
        state_store=ss,
        workflow_registry=MagicMock(),
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )

    protocol_errors = [
        {"location": "step:1", "type": "PROTOCOL_ERROR", "reason": "缺少动作字段", "suggestion": ""},
    ]
    with patch.object(tracker, "_check_protocol_errors", return_value=protocol_errors):
        context = {
            "final_artifact": "# wf",
            "evaluator_report": {"status": "APPROVED"},
            "prev_defects": [{"existing": "defect"}],
        }
        await tracker.on_run_end("run-1", context)

    assert len(context["prev_defects"]) == 1
    types = [d.get("type") for d in context["prev_defects"]]
    assert "PROTOCOL_ERROR" in types
    assert context["prev_defects_summary"]["previous_count"] == 1
    assert context["prev_defects_summary"]["latest_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 场景 5：on_run_end 成功注册 + 保存审计
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_on_run_end_successful_saves_audit_and_replay():
    """注册成功时，保存审计信息并调用回放。"""
    ss = _make_state_store()
    registry = MagicMock()
    registry.register_generated_workflow.return_value = {
        "workflow_id": "wf_test_001",
        "workflow_path": "/fake/wf_test_001.step.md",
        "protocol_summary": "ok",
        "protocol_report": {},
        "dry_run": {"status": "passed"},
    }
    tracker = ChampionTracker(
        state_store=ss,
        workflow_registry=registry,
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )

    with patch.object(tracker, "_check_protocol_errors", return_value=[]):
        with patch.object(tracker, "_attempt_replay", new_callable=AsyncMock) as mock_replay:
            context = {
                "final_artifact": "# wf",
                "evaluator_report": {"status": "APPROVED"},
            }
            await tracker.on_run_end("run-1", context)

    assert context["workflow_id"] == "wf_test_001"
    assert context["generated_workflow_path"] == "/fake/wf_test_001.step.md"
    ss.save_run_meta.assert_called_once()
    audit = ss.save_run_meta.call_args.kwargs.get("registration_audit")
    assert audit["workflow_id"] == "wf_test_001"
    mock_replay.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 场景 6：Champion 分数对比（高分更新 / 低分保留）
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_higher_score_replaces_champion():
    """APPROVED 且新分数 > 旧分数时，champion_json 被替换。"""
    ss = _make_state_store()
    old_champion = {"score": 70, "evaluator_report": {"status": "APPROVED", "score": 70}}
    ss.load_run_meta.return_value = {"champion_json": old_champion}

    tracker = ChampionTracker(
        state_store=ss,
        workflow_registry=MagicMock(),
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )
    tracker._current_run_id = "run-1"

    context = {"final_artifact": "# new wf"}
    report = {"status": "APPROVED", "score": 95, "overall_feedback": "excellent"}
    await tracker._update_champion(context, report)

    assert context["champion_json"]["score"] == 95
    saved_champion = ss.save_run_meta.call_args.kwargs.get("champion_json")
    assert saved_champion["score"] == 95


@pytest.mark.asyncio
async def test_lower_score_keeps_existing_champion():
    """APPROVED 但新分数 < 旧分数时，champion_json 保持旧值。"""
    ss = _make_state_store()
    old_champion = {"score": 95, "evaluator_report": {"status": "APPROVED", "score": 95}}
    ss.load_run_meta.return_value = {"champion_json": old_champion}

    tracker = ChampionTracker(
        state_store=ss,
        workflow_registry=MagicMock(),
        protocol_service=MagicMock(),
        workflows_root="/fake",
    )
    tracker._current_run_id = "run-1"

    context = {}
    report = {"status": "APPROVED", "score": 60, "overall_feedback": "ok"}
    await tracker._update_champion(context, report)

    assert context["champion_json"] == old_champion
