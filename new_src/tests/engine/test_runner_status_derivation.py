"""Runner 最终状态派生语义测试。"""
from __future__ import annotations

from agent.engine.runner import Runner


def _runner() -> Runner:
    return Runner.__new__(Runner)


def test_non_meta_workflow_keeps_success_semantics():
    runner = _runner()
    status = runner._derive_final_status(
        {"evaluator_report": {"status": "REJECTED"}},
        "Quality Evaluator",
    )
    assert status == "success"


def test_meta_workflow_without_report_returns_success():
    runner = _runner()
    status = runner._derive_final_status({}, "Meta Main Workflow")
    assert status == "success"


def test_meta_workflow_rejected_report_returns_rejected():
    runner = _runner()
    status = runner._derive_final_status(
        {"evaluator_report": {"status": "REJECTED"}},
        "Meta Main Workflow",
    )
    assert status == "rejected"


def test_meta_workflow_approved_without_replay_returns_unverified():
    runner = _runner()
    status = runner._derive_final_status(
        {"evaluator_report": {"status": "APPROVED", "score": 80}},
        "Meta Main Workflow",
    )
    assert status == "approved_unverified"


def test_meta_workflow_approved_with_replay_success_returns_success():
    runner = _runner()
    status = runner._derive_final_status(
        {
            "evaluator_report": {"status": "APPROVED", "score": 80},
            "generated_workflow_replay": {"status": "success"},
        },
        "Meta Main Workflow",
    )
    assert status == "success"


def test_meta_workflow_approved_with_replay_failure_returns_replay_failed():
    runner = _runner()
    status = runner._derive_final_status(
        {
            "evaluator_report": {"status": "APPROVED", "score": 80},
            "generated_workflow_replay": {"status": "failed"},
        },
        "Meta Main Workflow",
    )
    assert status == "replay_failed"


def test_meta_workflow_approved_low_score_returns_rejected():
    runner = _runner()
    status = runner._derive_final_status(
        {
            "evaluator_report": {"status": "APPROVED", "score": 10},
            "generated_workflow_replay": {"status": "success"},
        },
        "Meta Main Workflow",
    )
    assert status == "rejected"


def test_skip_auto_replay_always_returns_success():
    runner = _runner()
    status = runner._derive_final_status(
        {
            "__skip_auto_replay__": True,
            "evaluator_report": {"status": "REJECTED"},
        },
        "Meta Main Workflow",
    )
    assert status == "success"
