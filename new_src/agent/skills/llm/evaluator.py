"""Evaluator 技能：四维质量门禁审查。

核心变更（design.md）：
  - 静态扫描改为接受 WorkflowModel 对象（不再依赖 Markdown 文本）
  - 四维评分标准外化到系统 Prompt 文件
  - 继承 LLMAgentSpec，复用结构化 LLM 工厂
"""
from __future__ import annotations

import logging
from typing import Any

from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.security_scan import scan_workflow_model
from agent.skills.base import IdempotencyLevel, LLMAgentSpec
from agent.skills.llm.types import Defect, EvaluatorReport

logger = logging.getLogger(__name__)


class LLMEvaluatorCall(LLMAgentSpec):
    """Evaluator 技能：先对 WorkflowModel 做确定性静态扫描，再用 LLM 执行语义评审。

    接受来自 Generator 的 ``WorkflowModel`` 或退化的 Markdown 文本（向后兼容）。
    静态扫描优先，命中安全违规则直接 REJECTED，不消耗 LLM token。
    """

    name = "llm_evaluator_call"
    description = "对 WorkflowModel 执行四维质量门禁（安全扫描 + LLM 语义评审）"
    when_to_use = "有 final_artifact 需要质量审核时"
    do_not_use_when = "不需要质量审核或测试流程中跳过评审时"
    idempotency = IdempotencyLevel.L0
    system_prompt_path = "evaluator_system_v1.md"
    default_temperature = 0.0

    def __init__(self) -> None:
        super().__init__()
        self._structured_llm = self._get_structured_llm(EvaluatorReport)

    # ── 静态扫描 ──────────────────────────────────────────────────────────

    @staticmethod
    def _static_scan_model(model: WorkflowModel) -> dict:
        """对 WorkflowModel 执行确定性静态扫描。"""
        result = scan_workflow_model(model)
        return {
            "violations": list(result.violations),
            "warnings": list(result.warnings),
            "clean": result.clean,
        }

    @staticmethod
    def _build_static_rejection(scan_result: dict) -> dict:
        defects = [
            Defect(
                location="Global (静态扫描)",
                type="SAFETY_VIOLATION",
                reason=v,
                suggestion="在对应步骤标题行添加 [DANGER] 或 [CONFIRM] 标记",
            )
            for v in scan_result["violations"]
        ]
        return EvaluatorReport(
            status="REJECTED",
            score=0,
            dimension_scores={
                "logic_closure": 100,
                "safety_gate": 0,
                "engineering_quality": 0,
                "persona_adherence": 0,
            },
            defects=defects,
            overall_feedback=(
                f"静态扫描发现 {len(scan_result['violations'])} 处安全违规，"
                "请先修复后再进行语义审查。"
            ),
        ).model_dump()

    @staticmethod
    def _build_precheck_rejection(precheck_defects: list[dict], summary: str | None = None) -> dict:
        defects = [
            Defect(
                location=str(item.get("location") or "workflow:precheck"),
                type="LOGIC_ERROR" if str(item.get("type") or "") != "PROTOCOL_ERROR" else "QUALITY_ISSUE",
                reason=str(item.get("reason") or "生成前置校验失败"),
                suggestion=str(item.get("suggestion") or "请根据缺陷修复并重试生成。"),
            )
            for item in precheck_defects
            if isinstance(item, dict)
        ]
        feedback = summary or "Generator 前置校验未通过，已跳过 LLM 语义评审。"
        return EvaluatorReport(
            status="REJECTED",
            score=0,
            dimension_scores={
                "logic_closure": 0,
                "safety_gate": 0,
                "engineering_quality": 0,
                "persona_adherence": 0,
            },
            defects=defects,
            overall_feedback=feedback,
        ).model_dump()

    # ── 主入口 ────────────────────────────────────────────────────────────

    async def execute_step(self, step: dict, context: dict) -> dict:
        artifact = context.get("final_artifact")
        escalation_level = context.get("escalation_level", 1)
        prev_defects = list(context.get("prev_defects") or [])
        precheck_defects = list(context.get("pre_evaluator_defects") or [])
        if precheck_defects:
            logger.warning("⚠️ [Evaluator] 检测到 pre_evaluator_defects，跳过 LLM 评审。")
            return {
                "evaluator_report": self._build_precheck_rejection(
                    precheck_defects,
                    summary=str(context.get("generator_validation_feedback") or ""),
                )
            }
        return await self._run(artifact, escalation_level, prev_defects)

    async def _run(self, artifact: Any, escalation_level: int, prev_defects: list[dict] | None = None) -> dict:
        # ── 空值快速失败 ──────────────────────────────────────────────────
        if artifact is None or (isinstance(artifact, str) and not artifact.strip()):
            logger.warning("⚠️ Evaluator 收到空的 final_artifact，返回 REJECTED。")
            return {
                "evaluator_report": EvaluatorReport(
                    status="REJECTED",
                    score=0,
                    dimension_scores={},
                    defects=[
                        Defect(
                            location="Global",
                            type="LOGIC_ERROR",
                            reason="final_artifact 为空",
                            suggestion="确认 Generator 已正确输出 final_artifact",
                        )
                    ],
                    overall_feedback="待审核内容为空，无法评审。",
                ).model_dump()
            }

        # ── Step 1：静态扫描（规则优先，不过 LLM）────────────────────────
        logger.info("🔍 [Evaluator] 执行静态安全扫描...")

        if isinstance(artifact, WorkflowModel):
            scan_result = self._static_scan_model(artifact)
            artifact_text = artifact.to_markdown()
        else:
            # 退化路径：旧版 Markdown 字符串兼容
            from agent.engine.protocol.security_scan import scan_artifact_security
            raw = scan_artifact_security(str(artifact))
            scan_result = {
                "violations": list(raw.violations),
                "warnings": list(raw.warnings),
                "clean": raw.clean,
            }
            artifact_text = str(artifact)

        if scan_result["warnings"]:
            logger.warning(
                "⚠️  静态扫描发现 %d 条警告（不阻断）: %s",
                len(scan_result["warnings"]),
                scan_result["warnings"],
            )

        if not scan_result["clean"]:
            logger.error(
                "🛑 静态扫描命中 %d 处安全违规，快速失败。",
                len(scan_result["violations"]),
            )
            return {"evaluator_report": self._build_static_rejection(scan_result)}

        # ── Step 2：LLM 结构化语义评审 ────────────────────────────────────
        logger.info("🤖 [Evaluator] 调用 LLM 进行四维语义评审（第 %d 轮）...", escalation_level)

        system_prompt = self._load_system_prompt()
        static_summary = "静态扫描通过，无安全关键词违规。" + (
            f"警告项（仅供参考）: {scan_result['warnings']}"
            if scan_result["warnings"]
            else ""
        )

        prompt = (
            f"{system_prompt}\n\n"
            f"━━━━━━━━━━ 静态扫描结果（规则确定，不可推翻）━━━━━━━━━━\n"
            f"{static_summary}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"当前审查轮次：{escalation_level}\n\n"
            f"历史缺陷反馈：{prev_defects or []}\n\n"
            f"待审核工作流：\n{artifact_text}"
        )

        try:
            report: EvaluatorReport = await self._structured_llm.ainvoke(prompt)
        except Exception as e:
            logger.error("🔴 LLM 结构化调用失败: %s", e)
            raise

        logger.info(
            "📊 Evaluator 评审完成: status=%s, score=%s, defects=%d",
            report.status,
            report.score,
            len(report.defects),
        )
        return {"evaluator_report": report.model_dump()}
