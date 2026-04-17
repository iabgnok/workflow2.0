"""Generator 技能：基于蓝图生成结构化工作流。

核心变更（design.md Decision 3）：
  消除文本往返 —— LLM 直接输出 StructuredWorkflowArtifact，
  不经过 Markdown 渲染再解析，直接转换为 WorkflowModel。
"""
from __future__ import annotations

import json
import logging
from difflib import get_close_matches
from typing import Any

from agent.engine.protocol.models import WorkflowMetadata, WorkflowModel, WorkflowStep
from agent.engine.protocol.report import MACHINE_FIXABLE_CODES
from agent.engine.protocol.service import ProtocolService
from agent.skills.base import IdempotencyLevel, LLMAgentSpec
from agent.skills.llm.types import StructuredWorkflowArtifact
from config.settings import settings

logger = logging.getLogger(__name__)


class LLMGeneratorCall(LLMAgentSpec):
    """Generator 技能：将 Planner 蓝图转换为 WorkflowModel。

    使用 Pydantic structured output 强制 LLM 按 StructuredWorkflowArtifact
    格式输出，然后直接转换为 WorkflowModel，跳过 Markdown 中间格式。
    """

    name = "llm_generator_call"
    description = "基于工作流蓝图，调用 LLM 生成结构化工作流对象（WorkflowModel）"
    when_to_use = "有 workflow_blueprint 且需要生成可执行工作流时"
    do_not_use_when = "蓝图为空，或只需要自然语言回复时"
    idempotency = IdempotencyLevel.L2
    system_prompt_path = "generator_system_v1.md"
    default_temperature = 0.1

    def __init__(self) -> None:
        super().__init__()
        self._protocol_service = ProtocolService()
        try:
            self._structured_llm = self._get_structured_llm(StructuredWorkflowArtifact)
        except Exception as e:
            logger.error("❌ Generator LLM 初始化失败: %s", e)
            self._structured_llm = None

    # ── 辅助方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _dedupe_names(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in values:
            text = str(item or "").strip().strip("`")
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    def _validate_actions(
        self, artifact: StructuredWorkflowArtifact, registered_skills: list[str]
    ) -> None:
        if not registered_skills:
            return
        allowed = set(registered_skills)
        unknown = sorted({s.action for s in artifact.steps if s.action not in allowed})
        if unknown:
            raise ValueError(f"WF_UNKNOWN_ACTIONS: 使用了未注册的技能: {unknown}")

    @staticmethod
    def _closest_skill(action: str, registered_skills: list[str]) -> str | None:
        if not action or not registered_skills:
            return None
        matches = get_close_matches(action, registered_skills, n=1, cutoff=0.72)
        return matches[0] if matches else None

    @staticmethod
    def _extract_blueprint_action_types(blueprint: Any) -> list[str]:
        parsed = blueprint
        if isinstance(blueprint, str):
            try:
                parsed = json.loads(blueprint)
            except json.JSONDecodeError:
                return []
        if not isinstance(parsed, dict):
            return []

        raw_steps = parsed.get("main_flow_steps")
        if not isinstance(raw_steps, list):
            return []

        result: list[str] = []
        for item in raw_steps:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type") or "").strip()
            if action_type:
                result.append(action_type)
        return result

    def _normalize_actions(
        self,
        artifact: StructuredWorkflowArtifact,
        registered_skills: list[str],
        blueprint_action_types: list[str],
    ) -> tuple[list[dict], list[dict]]:
        if not registered_skills:
            return [], []

        allowed = set(registered_skills)
        audits: list[dict] = []
        defects: list[dict] = []

        for idx, spec in enumerate(artifact.steps, start=1):
            original = str(spec.action or "").strip()
            if original in allowed:
                continue

            blueprint_action = ""
            if idx - 1 < len(blueprint_action_types):
                blueprint_action = str(blueprint_action_types[idx - 1] or "").strip()

            resolved = ""
            reason = ""
            if blueprint_action and blueprint_action in allowed:
                resolved = blueprint_action
                reason = "mapped_from_blueprint_action_type"
            else:
                closest = self._closest_skill(original, registered_skills)
                if closest:
                    resolved = closest
                    reason = "fuzzy_match"
                elif blueprint_action:
                    closest = self._closest_skill(blueprint_action, registered_skills)
                    if closest:
                        resolved = closest
                        reason = "fuzzy_match_from_blueprint_action_type"

            if resolved:
                spec.action = resolved
                audits.append(
                    {
                        "step_id": idx,
                        "step_name": spec.name,
                        "original_action": original,
                        "resolved_action": resolved,
                        "reason": reason,
                    }
                )
                continue

            defects.append(
                {
                    "location": f"step:{idx}",
                    "type": "LOGIC_ERROR",
                    "code": "WF_UNKNOWN_ACTIONS",
                    "fix_category": "model-fixable",
                    "reason": f"Step action 未注册且无法自动修复: {original}",
                    "suggestion": "请将 action 修正为 registered_skills 白名单中的值。",
                }
            )

        return audits, defects

    @staticmethod
    def _protocol_defects(validation_result: dict[str, Any]) -> list[dict]:
        report = validation_result.get("protocol_report") or {}
        issues = report.get("issues") or []
        defects: list[dict] = []
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            if issue.get("level") != "error":
                continue
            code = str(issue.get("code") or "")
            defects.append(
                {
                    "location": str(issue.get("location") or "workflow:protocol"),
                    "type": "PROTOCOL_ERROR",
                    "code": code,
                    "fix_category": "machine-fixable" if code in MACHINE_FIXABLE_CODES else "model-fixable",
                    "reason": str(issue.get("message") or "协议检查失败"),
                    "suggestion": str(issue.get("suggestion") or "请根据协议错误修正结构化字段。"),
                }
            )
        return defects

    @staticmethod
    def _to_workflow_model(artifact: StructuredWorkflowArtifact) -> WorkflowModel:
        """将 StructuredWorkflowArtifact 直接转换为 WorkflowModel（无 Markdown 中间层）。"""
        steps: list[WorkflowStep] = []
        for idx, spec in enumerate(artifact.steps, start=1):
            inputs_deduped = LLMGeneratorCall._static_dedupe(list(spec.inputs or []))
            outputs_deduped = LLMGeneratorCall._static_dedupe(list(spec.outputs or []))
            synthetic_parts = [
                (spec.name or "").strip(),
                (spec.action or "").strip(),
                f"inputs: {', '.join(inputs_deduped)}" if inputs_deduped else "",
                f"outputs: {', '.join(outputs_deduped)}" if outputs_deduped else "",
            ]
            synthetic_content = " | ".join(part for part in synthetic_parts if part)
            steps.append(
                WorkflowStep(
                    id=idx,
                    name=(spec.name or f"Step {idx}").strip(),
                    action=spec.action.strip(),
                    content=synthetic_content,
                    inputs={v: v for v in inputs_deduped},
                    outputs={v: v for v in outputs_deduped},
                    condition=spec.condition,
                    workflow=spec.workflow,
                    on_reject=spec.on_reject,
                    require_confirm=spec.require_confirm,
                )
            )
        return WorkflowModel(
            metadata=WorkflowMetadata(
                name=artifact.workflow_name.strip(),
                description=artifact.description.strip() or None,
                inputs=LLMGeneratorCall._static_dedupe(list(artifact.inputs or [])),
                outputs=LLMGeneratorCall._static_dedupe(list(artifact.outputs or [])),
            ),
            steps=steps,
        )

    @staticmethod
    def _static_dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for v in values:
            text = str(v or "").strip().strip("`")
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    # ── 运行入口 ──────────────────────────────────────────────────────────

    async def execute_step(self, step: dict, context: dict) -> dict:
        if not self._structured_llm:
            raise ValueError("Generator 的 LLM 客户端未成功初始化，无法执行。")
        if not hasattr(self, "_protocol_service") or self._protocol_service is None:
            self._protocol_service = ProtocolService()

        blueprint = context.get("workflow_blueprint", "{}")
        prev_defects = list(context.get("prev_defects", []) or [])
        prev_defects_summary = context.get("prev_defects_summary")
        escalation_level = context.get("escalation_level", 1)
        registered_skills: list[str] = context.get("registered_skills") or []
        max_validation_retries = int(
            context.get("structured_validation_max_retries", settings.structured_validation_max_retries)
        )
        max_validation_retries = max(0, max_validation_retries)

        # 构建技能 Manifest
        skill_manifest = self._build_skill_manifest(registered_skills)
        blueprint_action_types = self._extract_blueprint_action_types(blueprint)

        # 加载系统 Prompt（带缓存）
        try:
            system_prompt = self._load_system_prompt()
        except (ValueError, FileNotFoundError):
            system_prompt = ""

        rolling_defects: list[dict] = []
        latest_audits: list[dict] = []
        last_validation_summary = "ok"
        last_explanation = ""
        last_workflow_model: WorkflowModel | None = None

        for attempt in range(1, max_validation_retries + 2):
            retry_context = self._build_retry_context(
                prev_defects=prev_defects + rolling_defects,
                escalation_level=escalation_level,
                prev_defects_summary=prev_defects_summary,
                validation_attempt=attempt,
                max_validation_retries=max_validation_retries,
            )
            prompt = self._build_prompt(system_prompt, blueprint, skill_manifest, retry_context)

            is_retry = bool(prev_defects or rolling_defects)
            logger.info(
                "💻 [Generator] 正在%s生成工作流（预检尝试 %d/%d）...",
                "修复草案并" if is_retry else "",
                attempt,
                max_validation_retries + 1,
            )

            try:
                artifact: Any = await self._structured_llm.ainvoke(prompt)
            except Exception as e:
                logger.error("🔴 Generator 生成失败: %s", repr(e))
                raise

            if not isinstance(artifact, StructuredWorkflowArtifact):
                raise ValueError(f"Generator 返回未知结构类型: {type(artifact)}")

            action_audits, action_defects = self._normalize_actions(
                artifact=artifact,
                registered_skills=registered_skills,
                blueprint_action_types=blueprint_action_types,
            )
            workflow_model = self._to_workflow_model(artifact)
            validation_result = self._protocol_service.validate_workflow_model(
                workflow_model,
                registered_skills=registered_skills,
                available_context=context,
            )
            protocol_defects = self._protocol_defects(validation_result)

            latest_audits = action_audits
            last_workflow_model = workflow_model
            last_validation_summary = str(validation_result.get("summary") or "ok")
            last_explanation = str(artifact.explanation or "")

            current_defects = action_defects + protocol_defects
            if not current_defects:
                logger.info("✅ Generator 生成完成，反馈: %s", artifact.explanation)
                return {
                    "final_artifact": workflow_model,
                    "action_normalization_audit": action_audits,
                    "generator_validation_summary": "ok",
                    "generator_validation_retry_count": attempt - 1,
                }

            rolling_defects = current_defects
            logger.warning(
                "⚠️ [Generator] 预检未通过（尝试 %d/%d）：%s",
                attempt,
                max_validation_retries + 1,
                last_validation_summary,
            )

        logger.warning("⚠️ [Generator] 预检重试耗尽，缺陷将回流 Evaluator 前置拒绝路径。")
        return {
            "final_artifact": last_workflow_model,
            "pre_evaluator_defects": rolling_defects,
            "action_normalization_audit": latest_audits,
            "generator_validation_summary": last_validation_summary,
            "generator_validation_feedback": (
                f"结构化预检失败，已重试 {max_validation_retries} 次。"
                f"最后说明：{last_explanation or '无额外说明'}"
            ),
            "generator_validation_retry_count": max_validation_retries,
        }

    # ── 私有：Prompt 构建 ─────────────────────────────────────────────────

    @staticmethod
    def _build_skill_manifest(registered_skills: list[str]) -> str:
        if not registered_skills:
            return "- (empty)"
        return "\n".join(f"- {s}" for s in registered_skills)

    @staticmethod
    def _build_retry_context(
        prev_defects: list,
        escalation_level: int,
        prev_defects_summary: Any = None,
        validation_attempt: int = 1,
        max_validation_retries: int = 0,
    ) -> str:
        summary_text = ""
        if prev_defects_summary:
            summary_text = f"上一轮修复摘要：{prev_defects_summary}\n"

        if not prev_defects:
            return (
                f"\n结构化预检重试信息：第 {validation_attempt}/{max_validation_retries + 1} 次。\n"
                f"{summary_text}"
            )

        return (
            f"\n━━━━━━━━━━ 前期缺陷反馈 (Escalation Level: {escalation_level}) ━━━━━━━━━━\n"
            f"结构化预检重试：第 {validation_attempt}/{max_validation_retries + 1} 次。\n"
            f"{summary_text}"
            f"你的上一版草案被打回，这是最新缺陷清单：\n{prev_defects}\n"
            "请优先修复 machine-fixable 缺陷，再处理 model-fixable 缺陷。\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

    @staticmethod
    def _build_prompt(
        system_prompt: str,
        blueprint: str,
        skill_manifest: str,
        retry_context: str,
    ) -> str:
        header = (system_prompt + "\n\n") if system_prompt else ""
        return (
            f"{header}"
            f"━━━━━━━━━━━━━━ 工作流设计蓝图 ━━━━━━━━━━━━━━\n"
            f"{blueprint}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"━━━━━━━━━━━━━━ 当前可用技能清单（仅可从此列表选择 Action）━━━━━━━━━━━━━━\n"
            f"{skill_manifest}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{retry_context}"
        )
