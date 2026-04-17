"""E2E 测试 Test 1：真实 LLM 驱动的 Meta Main Workflow 端到端测试。

通过 run_meta_workflow() 传入自然语言需求，驱动
Planner → Designer → Evaluator 完整链路，断言输出为合法 WorkflowModel。

需要 .env 中配置 DEEPSEEK_API_KEY 才会运行。
"""
from __future__ import annotations

import os
import sys

import pytest
from config.settings import settings
from tests.e2e.conftest import has_deepseek_api_key

# 将 new_src 加入 sys.path（兼容直接运行）
_new_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _new_src not in sys.path:
    sys.path.insert(0, _new_src)


def _force_utf8_stdio() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


_force_utf8_stdio()

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not has_deepseek_api_key(),
        reason="DEEPSEEK_API_KEY not set",
    ),
]

# Meta Main Workflow 绝对路径
_META_WORKFLOW_FILE = os.path.abspath(
    os.path.join(_new_src, "agent", "workflows", "meta", "main_workflow.step.md")
)
_WORKFLOWS_ROOT = os.path.abspath(os.path.join(_new_src, "agent", "workflows"))


async def test_meta_workflow_generates_valid_workflow_model():
    """Test 1：给定自然语言需求，Meta Main Workflow 输出合法 WorkflowModel。"""
    from main import run_meta_workflow
    from agent.engine.protocol.models import WorkflowModel

    result = await run_meta_workflow(
        filepath=_META_WORKFLOW_FILE,
        initial_context={
            "requirement": (
                "构建一个 3 步工作流：读取文本文件、调用 LLM 生成摘要、写回文件。"
                "Action 只允许 file_reader、llm_prompt_call、file_writer，不要使用其它 Action。"
            )
        },
        workflows_root=_WORKFLOWS_ROOT,
        db_path=":memory:",
    )

    # 断言运行成功（包含 replay 与注册诊断，便于定位失败阶段）
    context = result.get("context", {})
    replay_diag = context.get("generated_workflow_replay")
    registration_diag = context.get("generated_workflow_registration_summary")
    assert result["status"] == "success", (
        f"Meta workflow 执行失败，status={result.get('status')}, "
        f"replay={replay_diag}, registration={registration_diag}"
    )

    report = context.get("evaluator_report") or {}
    score = int(report.get("score", -1)) if isinstance(report, dict) else -1
    assert report.get("status") == "APPROVED", f"Evaluator 未通过: report={report}"
    assert score >= settings.min_quality_score, (
        f"Evaluator 分数低于阈值: score={score}, min_quality_score={settings.min_quality_score}"
    )

    # 断言 final_artifact 是合法的 WorkflowModel
    final_artifact = context.get("final_artifact")
    assert final_artifact is not None, "context 中缺少 final_artifact"
    assert isinstance(final_artifact, WorkflowModel), (
        f"final_artifact 应为 WorkflowModel，实际为 {type(final_artifact)}"
    )

    # 断言步骤非空
    assert len(final_artifact.steps) > 0, "WorkflowModel.steps 不应为空"

    # 断言 metadata.name 非空
    assert final_artifact.metadata.name and final_artifact.metadata.name != "UNKNOWN", (
        f"WorkflowModel.metadata.name 应为非空字符串，实际为 {final_artifact.metadata.name!r}"
    )

    # 断言每个 step 的 action 为非空字符串
    for step in final_artifact.steps:
        assert step.action and step.action != "unknown", (
            f"Step {step.id} 的 action 字段为空或 'unknown'"
        )


@pytest.mark.slow
async def test_meta_workflow_success_rate_at_least_seventy_percent():
    """Test 1 slow：运行 20 次，并记录失败阶段分布。"""
    from main import run_meta_workflow

    total_runs = 20
    counts = {
        "quality_pass": 0,
        "quality_fail": 0,
        "rejected": 0,
        "approved_unverified": 0,
        "replay_failed": 0,
        "other": 0,
    }
    failure_samples: list[dict[str, str]] = []

    for idx in range(1, total_runs + 1):
        try:
            result = await run_meta_workflow(
                filepath=_META_WORKFLOW_FILE,
                initial_context={
                    "requirement": (
                        "构建一个 3 步工作流：读取文本文件、调用 LLM 生成摘要、写回文件。"
                        "Action 只允许 file_reader、llm_prompt_call、file_writer，不要使用其它 Action。"
                    )
                },
                workflows_root=_WORKFLOWS_ROOT,
                db_path=":memory:",
            )
            status = str(result.get("status") or "")
            context = result.get("context", {})
            replay_diag = context.get("generated_workflow_replay")
            report = context.get("evaluator_report") or {}
            try:
                score = int(report.get("score", -1))
            except (TypeError, ValueError):
                score = -1
            evaluator_status = str(report.get("status") or "")

            is_quality_pass = (
                status == "success"
                and evaluator_status == "APPROVED"
                and score >= settings.min_quality_score
            )
            if is_quality_pass:
                counts["quality_pass"] += 1
            else:
                counts["quality_fail"] += 1
                if status in counts:
                    counts[status] += 1
                else:
                    counts["other"] += 1
                failure_samples.append(
                    {
                        "run": str(idx),
                        "status": status,
                        "evaluator_status": evaluator_status,
                        "score": str(score),
                        "threshold": str(settings.min_quality_score),
                        "validation_summary": str(context.get("generator_validation_summary")),
                        "replay": str(replay_diag),
                    }
                )
        except Exception as exc:
            counts["quality_fail"] += 1
            failure_samples.append(
                {
                    "run": str(idx),
                    "status": "exception",
                    "replay": str(exc),
                }
            )

    quality_pass_count = counts["quality_pass"]
    assert quality_pass_count >= 14, (
        "Meta workflow success rate below 70% | "
        f"counts={counts} | "
        f"failure_samples={failure_samples[:5]}"
    )
