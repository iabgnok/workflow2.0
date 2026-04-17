"""集成测试：Runner + 子模块（任务 8.1-8.3）

使用 mock StateStore、SkillRegistry、ProtocolService 隔离外部依赖，
只测试 Runner 的编排逻辑（条件、on_reject、断点恢复）。
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.engine.runner import Runner, EscalationLimitExceeded
from agent.engine.execution_hooks import ExecutionHooks, StepHookResult
from agent.engine.execution_observer import ExecutionObserver


# ── 测试辅助工厂 ──────────────────────────────────────────────────────────────

def _make_step(step_id, action="dummy_skill", condition=None, on_reject=None,
               inputs=None, outputs=None, name=None):
    return {
        "id": step_id,
        "name": name or f"Step {step_id}",
        "action": action,
        "content": f"step {step_id} content",
        "condition": condition,
        "on_reject": on_reject,
        "inputs": inputs or {},
        "outputs": outputs or {"out": "out"},
    }


def _make_wf_model(steps):
    model = MagicMock()
    model.metadata.name = "TestWF"
    return model, {"steps": steps}


def _make_state_store(run_state=None, latest_step=None):
    ss = MagicMock()
    ss.connect = AsyncMock()
    ss.close = AsyncMock()
    ss.load_run_state = AsyncMock(return_value=run_state)
    ss.load_latest_step_state = AsyncMock(return_value=latest_step)
    ss.save_run_state = AsyncMock()
    ss.save_step_state = AsyncMock()
    ss.save_run_meta = AsyncMock()
    return ss


def _make_skill(output=None):
    skill = MagicMock()
    del skill.execute_step
    skill.execute = AsyncMock(return_value=output or {})
    return skill


def _make_runner(steps, skill_output=None, state_store=None, hooks=None,
                 initial_context=None):
    """构造一个完全 mock 化的 Runner。"""
    ss = state_store or _make_state_store()

    skill = _make_skill(skill_output)
    registry = MagicMock()
    registry.get_all.return_value = {"dummy_skill": skill, "evaluator": skill}

    wf_model, parsed = _make_wf_model(steps)
    protocol = MagicMock()
    protocol.parse_workflow_file.return_value = (wf_model, parsed)
    protocol.validate_runtime_step_inputs.return_value = None
    protocol.validate_runtime_step_outputs.return_value = None

    async def fake_policy(skill_name, fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    observer = MagicMock(spec=ExecutionObserver)
    observer.on_step_start = AsyncMock()
    observer.on_step_end = AsyncMock()
    observer.flush = AsyncMock()

    runner = Runner.__new__(Runner)
    runner.filepath = "fake.step.md"
    runner.context = initial_context or {}
    runner.state_store = ss
    runner._skill_registry = registry
    runner._protocol = protocol
    runner._hooks = hooks or ExecutionHooks()
    runner._observer = observer

    from agent.engine.condition_evaluator import ConditionEvaluator
    from agent.engine.resume_strategy import ResumeStrategy
    from agent.engine.step_executor import StepExecutor
    from agent.engine.parser import WorkflowParser

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
# 8.1 完整步骤循环集成测试
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_full_two_step_loop_succeeds():
    steps = [_make_step(1), _make_step(2)]
    runner = _make_runner(steps, skill_output={"out": "value"})
    result = await runner.run()
    assert result["status"] == "success"
    assert result["run_id"] is not None


@pytest.mark.asyncio
async def test_single_step_context_updated():
    steps = [_make_step(1)]
    runner = _make_runner(steps, skill_output={"result": "done"})
    result = await runner.run()
    assert runner.context.get("result") == "done"


@pytest.mark.asyncio
async def test_step_skipped_by_condition():
    steps = [
        _make_step(1, condition="False"),   # 被跳过
        _make_step(2),
    ]
    ss = _make_state_store()
    runner = _make_runner(steps, state_store=ss)
    result = await runner.run()
    assert result["status"] == "success"
    # Step 1 被跳过，不应保存 step_state
    saved_ids = [call.args[1] for call in ss.save_step_state.call_args_list]
    assert 1 not in saved_ids
    assert 2 in saved_ids


@pytest.mark.asyncio
async def test_hook_before_skip_prevents_execution():
    class SkipHooks(ExecutionHooks):
        async def on_step_before(self, step, context):
            return StepHookResult(skip=True)

    steps = [_make_step(1)]
    ss = _make_state_store()
    runner = _make_runner(steps, state_store=ss, hooks=SkipHooks())
    result = await runner.run()
    assert result["status"] == "success"
    assert ss.save_step_state.call_count == 0   # 步骤被跳过，未保存


@pytest.mark.asyncio
async def test_hook_after_exception_isolated():
    class BrokenAfterHooks(ExecutionHooks):
        async def on_step_after(self, step, output, context):
            raise RuntimeError("hook after 崩溃")

    steps = [_make_step(1)]
    runner = _make_runner(steps, hooks=BrokenAfterHooks())
    # Hook 异常被隔离，Runner 不应崩溃
    result = await runner.run()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_step_failure_raises_and_saves_failed_state():
    steps = [_make_step(1)]
    ss = _make_state_store()
    runner = _make_runner(steps, state_store=ss)

    # 让 execute 抛异常
    runner._executor.execute = AsyncMock(side_effect=ValueError("技能崩溃"))

    with pytest.raises(ValueError, match="技能崩溃"):
        await runner.run()

    # 应保存 failed 状态
    statuses = [call.args[2] for call in ss.save_step_state.call_args_list]
    assert "failed" in statuses


# ═══════════════════════════════════════════════════════════════════════════════
# 8.2 on_reject 路由 / Escalation Ladder 集成测试
# ═══════════════════════════════════════════════════════════════════════════════

def _make_evaluator_step(step_id, target_id, report_status="REJECTED"):
    """返回一个带 evaluator_report 输出的步骤配置。"""
    async def _execute(text_ctx, ctx):
        return {"evaluator_report": {"status": report_status, "defects": ["bad"], "overall_feedback": "fix it"}}

    skill = MagicMock()
    del skill.execute_step
    skill.execute = _execute
    return _make_step(step_id, action="evaluator", on_reject=target_id), skill


@pytest.mark.asyncio
async def test_on_reject_jumps_back_and_increments_escalation():
    """L1：REJECTED → 退回，escalation_level 变为 1。"""
    rejected_calls = {"count": 0}

    async def _eval_execute(text_ctx, ctx):
        rejected_calls["count"] += 1
        if rejected_calls["count"] == 1:
            return {"evaluator_report": {"status": "REJECTED", "defects": [], "overall_feedback": "bad"}}
        return {"evaluator_report": {"status": "APPROVED"}}

    steps = [
        _make_step(1, action="dummy_skill"),
        _make_step(2, action="evaluator", on_reject=1),
    ]
    ss = _make_state_store()

    dummy_skill = _make_skill({"out": "v"})
    eval_skill = MagicMock()
    del eval_skill.execute_step
    eval_skill.execute = _eval_execute

    registry = MagicMock()
    registry.get_all.return_value = {"dummy_skill": dummy_skill, "evaluator": eval_skill}

    wf_model, parsed = _make_wf_model(steps)
    protocol = MagicMock()
    protocol.parse_workflow_file.return_value = (wf_model, parsed)
    protocol.validate_runtime_step_inputs.return_value = None
    protocol.validate_runtime_step_outputs.return_value = None

    async def fake_policy(skill_name, fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    observer = MagicMock(spec=ExecutionObserver)
    observer.on_step_start = AsyncMock()
    observer.on_step_end = AsyncMock()
    observer.flush = AsyncMock()

    from agent.engine.condition_evaluator import ConditionEvaluator
    from agent.engine.resume_strategy import ResumeStrategy
    from agent.engine.step_executor import StepExecutor
    from agent.engine.parser import WorkflowParser

    runner = Runner.__new__(Runner)
    runner.filepath = "fake.step.md"
    runner.context = {}
    runner.state_store = ss
    runner._skill_registry = registry
    runner._protocol = protocol
    runner._hooks = ExecutionHooks()
    runner._observer = observer
    runner._evaluator = ConditionEvaluator()
    runner._resume = ResumeStrategy()
    runner._executor = StepExecutor(registry, protocol, WorkflowParser.replace_variables, fake_policy)

    result = await runner.run()
    assert result["status"] == "success"
    assert rejected_calls["count"] == 2     # 第一轮 REJECTED，第二轮 APPROVED


@pytest.mark.asyncio
async def test_escalation_limit_exceeded_raises():
    """L4：连续 4 轮 REJECTED → 抛 EscalationLimitExceeded。"""
    async def always_reject(text_ctx, ctx):
        return {"evaluator_report": {"status": "REJECTED", "defects": [], "overall_feedback": "bad"}}

    steps = [
        _make_step(1, action="dummy_skill"),
        _make_step(2, action="evaluator", on_reject=1),
    ]
    ss = _make_state_store()
    dummy_skill = _make_skill({"out": "v"})
    eval_skill = MagicMock(); del eval_skill.execute_step
    eval_skill.execute = always_reject

    registry = MagicMock()
    registry.get_all.return_value = {"dummy_skill": dummy_skill, "evaluator": eval_skill}

    wf_model, parsed = _make_wf_model(steps)
    protocol = MagicMock()
    protocol.parse_workflow_file.return_value = (wf_model, parsed)
    protocol.validate_runtime_step_inputs.return_value = None
    protocol.validate_runtime_step_outputs.return_value = None

    async def fake_policy(skill_name, fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    observer = MagicMock(spec=ExecutionObserver)
    observer.on_step_start = AsyncMock()
    observer.on_step_end = AsyncMock()
    observer.flush = AsyncMock()

    from agent.engine.condition_evaluator import ConditionEvaluator
    from agent.engine.resume_strategy import ResumeStrategy
    from agent.engine.step_executor import StepExecutor
    from agent.engine.parser import WorkflowParser

    runner = Runner.__new__(Runner)
    runner.filepath = "fake.step.md"
    runner.context = {}
    runner.state_store = ss
    runner._skill_registry = registry
    runner._protocol = protocol
    runner._hooks = ExecutionHooks()
    runner._observer = observer
    runner._evaluator = ConditionEvaluator()
    runner._resume = ResumeStrategy()
    runner._executor = StepExecutor(registry, protocol, WorkflowParser.replace_variables, fake_policy)

    with pytest.raises(EscalationLimitExceeded):
        await runner.run()


def test_reject_replaces_prev_defects_with_latest_round():
    steps = [_make_step(1, action="dummy_skill")]
    runner = _make_runner(
        steps,
        initial_context={
            "prev_defects": [
                {
                    "location": "step:0",
                    "type": "LOGIC_ERROR",
                    "reason": "old",
                    "suggestion": "old-fix",
                }
            ]
        },
    )
    counters = {}
    report = {
        "defects": [
            {
                "location": "step:1",
                "type": "QUALITY_ISSUE",
                "reason": "new",
                "suggestion": "new-fix",
            }
        ],
        "overall_feedback": "fix new defect",
    }

    target_idx = runner._reject(steps, steps[0], 1, report, counters)

    assert target_idx == 0
    assert runner.context["escalation_level"] == 1
    assert len(runner.context["prev_defects"]) == 1
    assert runner.context["prev_defects"][0]["location"] == "step:1"
    assert runner.context["prev_defects_summary"]["previous_count"] == 1
    assert runner.context["prev_defects_summary"]["latest_count"] == 1


def test_machine_fixable_reject_does_not_consume_budget_immediately():
    steps = [_make_step(1, action="dummy_skill")]
    runner = _make_runner(steps)
    counters = {}
    report = {
        "defects": [
            {
                "location": "step:1",
                "type": "PROTOCOL_ERROR",
                "fix_category": "machine-fixable",
                "reason": "auto-fixable",
                "suggestion": "auto-fix",
            }
        ],
        "overall_feedback": "machine fix first",
    }

    runner._reject(steps, steps[0], 1, report, counters)
    runner._reject(steps, steps[0], 1, report, counters)
    assert counters.get(1, 0) == 0

    runner._reject(steps, steps[0], 1, report, counters)
    assert counters.get(1, 0) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 8.3 断点恢复集成测试
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resume_from_checkpoint_skips_completed_steps():
    """有历史记录时，Runner 从 step 2 开始（step 1 已完成）。"""
    steps = [_make_step(1), _make_step(2)]
    ss = _make_state_store(
        run_state={"current_step_id": 2, "context": {"prev": "value"}, "meta_context": {}},
        latest_step={"step_id": 1, "full_context": {"prev": "value"}, "meta_full_context": {}},
    )
    runner = _make_runner(steps, state_store=ss)
    result = await runner.run(run_id="existing-run")
    assert result["status"] == "success"
    # 只应保存 step 2 的 success 状态（step 1 跳过恢复）
    saved_ids = [call.args[1] for call in ss.save_step_state.call_args_list]
    assert 2 in saved_ids
    assert 1 not in saved_ids


@pytest.mark.asyncio
async def test_resume_no_state_starts_fresh():
    """run_id 存在但无历史记录 → 从步骤 1 全新开始。"""
    steps = [_make_step(1)]
    ss = _make_state_store(run_state=None)
    runner = _make_runner(steps, state_store=ss)
    result = await runner.run(run_id="ghost-run")
    assert result["status"] == "success"
    saved_ids = [call.args[1] for call in ss.save_step_state.call_args_list]
    assert 1 in saved_ids
