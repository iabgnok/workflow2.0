"""单元测试：ChampionTracker 各钩子方法。"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.orchestration.champion_tracker import ChampionTracker, _parse_report
from agent.engine.execution_hooks import StepHookResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_tracker(**kwargs) -> tuple[ChampionTracker, MagicMock, MagicMock, MagicMock]:
    """构造 ChampionTracker 及其依赖的 Mock 对象。"""
    state_store = AsyncMock()
    state_store.load_latest_champion_by_composite = AsyncMock(return_value=None)
    state_store.load_run_meta = AsyncMock(return_value=None)
    state_store.save_run_meta = AsyncMock(return_value=None)

    workflow_registry = MagicMock()
    protocol_service = MagicMock()

    tracker = ChampionTracker(
        state_store=state_store,
        workflow_registry=workflow_registry,
        protocol_service=protocol_service,
        workflows_root="/fake/workflows",
        index_path=None,
        **kwargs,
    )
    return tracker, state_store, workflow_registry, protocol_service


# ── _parse_report ─────────────────────────────────────────────────────────────

def test_parse_report_dict():
    assert _parse_report({"status": "APPROVED"}) == {"status": "APPROVED"}


def test_parse_report_json_string():
    raw = json.dumps({"status": "REJECTED", "score": 55})
    result = _parse_report(raw)
    assert result["status"] == "REJECTED"
    assert result["score"] == 55


def test_parse_report_invalid_string():
    assert _parse_report("not json") == {}


def test_parse_report_none():
    assert _parse_report(None) == {}


# ── 私有工具方法 ───────────────────────────────────────────────────────────────

def test_requirement_fingerprint_stable():
    ctx = {"requirement": "生成一个文件读取工作流"}
    fp1 = ChampionTracker._requirement_fingerprint(ctx)
    fp2 = ChampionTracker._requirement_fingerprint(ctx)
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex


def test_requirement_fingerprint_empty():
    assert ChampionTracker._requirement_fingerprint({}) == ""
    assert ChampionTracker._requirement_fingerprint({"requirement": ""}) == ""


def test_blueprint_fingerprint_empty_context():
    assert ChampionTracker._blueprint_fingerprint({}) == ""


def test_blueprint_fingerprint_stable():
    bp = {
        "workflow_name": "TestWF",
        "main_flow_steps": [
            {"name": "步骤1", "action": "llm_call", "inputs": {"prompt": ""}, "outputs": {"result": ""}},
        ],
        "constraints": [],
    }
    ctx = {"workflow_blueprint": json.dumps(bp)}
    fp1 = ChampionTracker._blueprint_fingerprint(ctx)
    fp2 = ChampionTracker._blueprint_fingerprint(ctx)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_report_score_valid():
    assert ChampionTracker._report_score({"score": 85}) == 85


def test_report_score_missing():
    assert ChampionTracker._report_score({}) == -1


def test_report_score_non_numeric():
    assert ChampionTracker._report_score({"score": "abc"}) == -1


def test_report_score_non_dict():
    assert ChampionTracker._report_score("bad") == -1


# ── _hydrate_champion_context ─────────────────────────────────────────────────

def test_hydrate_sets_reuse_champion_when_approved():
    ctx = {}
    champion = {
        "score": 90,
        "final_artifact": "# workflow",
        "evaluator_report": {"status": "APPROVED"},
    }
    ChampionTracker._hydrate_champion_context(ctx, {"champion_json": champion})
    assert ctx["__reuse_champion__"] is True
    assert ctx["final_artifact"] == "# workflow"
    assert ctx["champion_json"] == champion


def test_hydrate_no_reuse_when_not_approved():
    ctx = {}
    champion = {
        "score": 40,
        "final_artifact": "# workflow",
        "evaluator_report": {"status": "REJECTED"},
    }
    ChampionTracker._hydrate_champion_context(ctx, {"champion_json": champion})
    assert ctx.get("__reuse_champion__") is None


def test_hydrate_empty_run_meta_no_op():
    ctx = {}
    ChampionTracker._hydrate_champion_context(ctx, {})
    assert ctx == {}


# ── on_run_start ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_on_run_start_no_fingerprint_skips_lookup():
    tracker, state_store, _, _ = make_tracker()
    context = {}  # 无 requirement，指纹为空
    await tracker.on_run_start("run-1", context)
    state_store.load_latest_champion_by_composite.assert_not_called()


@pytest.mark.asyncio
async def test_on_run_start_no_match_no_hydration():
    tracker, state_store, _, _ = make_tracker()
    state_store.load_latest_champion_by_composite.return_value = None
    context = {"requirement": "req", "workflow_blueprint": json.dumps({"workflow_name": "WF", "main_flow_steps": []})}
    await tracker.on_run_start("run-1", context)
    assert "__reuse_champion__" not in context


@pytest.mark.asyncio
async def test_on_run_start_match_hydrates_context():
    tracker, state_store, _, _ = make_tracker()
    champion = {
        "score": 88,
        "final_artifact": "# artifact",
        "evaluator_report": {"status": "APPROVED"},
    }
    state_store.load_latest_champion_by_composite.return_value = {
        "champion_json": champion
    }
    context = {
        "requirement": "req",
        "workflow_blueprint": json.dumps({"workflow_name": "WF", "main_flow_steps": []}),
    }
    await tracker.on_run_start("run-1", context)
    assert context["__reuse_champion__"] is True
    assert context["final_artifact"] == "# artifact"


# ── on_step_before ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_on_step_before_no_reuse_no_skip():
    tracker, _, _, _ = make_tracker()
    result = await tracker.on_step_before({"id": 2}, {})
    assert isinstance(result, StepHookResult)
    assert result.skip is False


@pytest.mark.asyncio
async def test_on_step_before_reuse_designer_skipped():
    tracker, _, _, _ = make_tracker()
    context = {"__reuse_champion__": True, "final_artifact": "# wf"}
    result = await tracker.on_step_before({"id": 2}, context)
    assert result.skip is True


@pytest.mark.asyncio
async def test_on_step_before_reuse_designer_no_artifact_not_skipped():
    tracker, _, _, _ = make_tracker()
    context = {"__reuse_champion__": True}  # 没有 final_artifact
    result = await tracker.on_step_before({"id": 2}, context)
    assert result.skip is False


@pytest.mark.asyncio
async def test_on_step_before_reuse_evaluator_skipped():
    tracker, _, _, _ = make_tracker()
    context = {"__reuse_champion__": True}
    result = await tracker.on_step_before({"id": 3}, context)
    assert result.skip is True


@pytest.mark.asyncio
async def test_on_step_before_reuse_other_step_not_skipped():
    tracker, _, _, _ = make_tracker()
    context = {"__reuse_champion__": True, "final_artifact": "# wf"}
    result = await tracker.on_step_before({"id": 1}, context)
    assert result.skip is False


@pytest.mark.asyncio
async def test_on_step_before_evaluator_injects_protocol_defects():
    tracker, _, _, _ = make_tracker()
    context = {"final_artifact": "# wf", "prev_defects": [{"type": "EXISTING"}]}
    with patch.object(
        tracker,
        "_check_protocol_errors",
        return_value=[{"type": "PROTOCOL_ERROR", "location": "step:1", "reason": "x", "suggestion": "y"}],
    ):
        result = await tracker.on_step_before({"id": 3}, context)

    assert result.skip is False
    assert len(context["prev_defects"]) == 1
    assert context["prev_defects"][0]["type"] == "PROTOCOL_ERROR"
    assert context["prev_defects_summary"]["previous_count"] == 1
    assert context["prev_defects_summary"]["latest_count"] == 1


@pytest.mark.asyncio
async def test_on_step_before_reuse_evaluator_still_skips_after_precheck():
    tracker, _, _, _ = make_tracker()
    context = {"__reuse_champion__": True, "final_artifact": "# wf"}
    with patch.object(tracker, "_check_protocol_errors", return_value=[]) as mock_check:
        result = await tracker.on_step_before({"id": 3}, context)

    assert result.skip is True
    mock_check.assert_called_once()


# ── on_step_after ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_on_step_after_no_evaluator_report_no_op():
    tracker, state_store, _, _ = make_tracker()
    tracker._current_run_id = "run-1"
    await tracker.on_step_after({"id": 3}, {}, {})
    state_store.save_run_meta.assert_not_called()


@pytest.mark.asyncio
async def test_on_step_after_rejected_saves_meta():
    tracker, state_store, _, _ = make_tracker()
    tracker._current_run_id = "run-1"
    output = {"evaluator_report": {"status": "REJECTED", "overall_feedback": "差"}}
    context = {}
    await tracker.on_step_after({"id": 3}, output, context)
    state_store.save_run_meta.assert_called_once()
    call_kwargs = state_store.save_run_meta.call_args
    assert call_kwargs.kwargs.get("champion_json") is None


@pytest.mark.asyncio
async def test_on_step_after_approved_higher_score_updates_champion():
    tracker, state_store, _, _ = make_tracker()
    tracker._current_run_id = "run-1"
    state_store.load_run_meta.return_value = None  # 无现有 champion
    output = {
        "evaluator_report": {"status": "APPROVED", "score": 90, "overall_feedback": "好"},
    }
    context = {"final_artifact": "# wf"}
    await tracker.on_step_after({"id": 3}, output, context)
    assert context["champion_json"]["score"] == 90
    state_store.save_run_meta.assert_called_once()
    saved_champion = state_store.save_run_meta.call_args.kwargs.get("champion_json")
    assert saved_champion is not None
    assert saved_champion["score"] == 90


@pytest.mark.asyncio
async def test_on_step_after_approved_lower_score_keeps_existing():
    tracker, state_store, _, _ = make_tracker()
    tracker._current_run_id = "run-1"
    existing_champion = {"score": 95, "evaluator_report": {"status": "APPROVED", "score": 95}}
    state_store.load_run_meta.return_value = {"champion_json": existing_champion}
    output = {
        "evaluator_report": {"status": "APPROVED", "score": 70, "overall_feedback": "一般"},
    }
    context = {}
    await tracker.on_step_after({"id": 3}, output, context)
    # champion_json 应保持现有高分
    assert context["champion_json"] == existing_champion


# ── on_run_end ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_on_run_end_skip_auto_replay_skips():
    tracker, state_store, registry, _ = make_tracker()
    context = {"__skip_auto_replay__": True}
    await tracker.on_run_end("run-1", context)
    registry.register_generated_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_on_run_end_no_artifact_skips():
    tracker, _, registry, _ = make_tracker()
    await tracker.on_run_end("run-1", {})
    registry.register_generated_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_on_run_end_not_approved_skips():
    tracker, _, registry, _ = make_tracker()
    context = {
        "final_artifact": "# wf",
        "evaluator_report": {"status": "REJECTED"},
    }
    await tracker.on_run_end("run-1", context)
    registry.register_generated_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_on_run_end_protocol_errors_flow_back():
    tracker, _, registry, _ = make_tracker()

    # _check_protocol_errors 返回错误列表
    with patch.object(tracker, "_check_protocol_errors", return_value=[
        {"location": "step:1", "type": "PROTOCOL_ERROR", "reason": "缺少动作", "suggestion": ""}
    ]):
        context = {
            "final_artifact": "# wf",
            "evaluator_report": {"status": "APPROVED"},
            "prev_defects": [],
        }
        await tracker.on_run_end("run-1", context)

    registry.register_generated_workflow.assert_not_called()
    assert len(context["prev_defects"]) == 1
    assert context["prev_defects"][0]["type"] == "PROTOCOL_ERROR"


@pytest.mark.asyncio
async def test_on_run_end_successful_registration():
    tracker, state_store, registry, _ = make_tracker()

    reg_info = {
        "workflow_id": "wf_001",
        "workflow_path": "/fake/wf_001.step.md",
        "protocol_summary": "ok",
        "protocol_report": {},
        "dry_run": {"status": "passed"},
    }
    registry.register_generated_workflow.return_value = reg_info

    with patch.object(tracker, "_check_protocol_errors", return_value=[]):
        with patch.object(tracker, "_attempt_replay", new_callable=AsyncMock) as mock_replay:
            context = {
                "final_artifact": "# wf",
                "evaluator_report": {"status": "APPROVED"},
            }
            await tracker.on_run_end("run-1", context)

    assert context["workflow_id"] == "wf_001"
    assert context["generated_workflow_path"] == "/fake/wf_001.step.md"
    state_store.save_run_meta.assert_called_once()
    mock_replay.assert_called_once_with("/fake/wf_001.step.md", context)


@pytest.mark.asyncio
async def test_on_run_end_registration_exception_flows_back():
    tracker, _, registry, _ = make_tracker()
    registry.register_generated_workflow.side_effect = ValueError("协议错误：缺少字段")

    with patch.object(tracker, "_check_protocol_errors", return_value=[]):
        context = {
            "final_artifact": "# wf",
            "evaluator_report": {"status": "APPROVED"},
            "prev_defects": [],
        }
        await tracker.on_run_end("run-1", context)

    assert len(context["prev_defects"]) == 1
    assert context["prev_defects"][0]["type"] == "PROTOCOL_ERROR"
