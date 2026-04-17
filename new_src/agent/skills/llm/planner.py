"""Planner 技能：将用户需求解构为工作流蓝图。

核心变更（design.md）：
  - 返回 workflow_blueprint 为 dict（model_dump()），而非 JSON 字符串
  - 系统 Prompt 外部化到 prompts/planner_system_v1.md
  - 继承 LLMAgentSpec
"""
from __future__ import annotations

import logging
from difflib import get_close_matches
from typing import List

from pydantic import BaseModel, Field

from agent.skills.base import IdempotencyLevel, LLMAgentSpec

logger = logging.getLogger(__name__)


# ── Pydantic 蓝图类型 ──────────────────────────────────────────────────────

class SubWorkflowBlueprint(BaseModel):
    name: str = Field(description="子工作流的名称")
    inputs: List[str] = Field(description="子工作流所需参数的键名列表")
    outputs: List[str] = Field(description="子工作流产出结果的键名列表")
    steps_description: str = Field(description="该子工作流内部步骤的简要说明")


class StepBlueprint(BaseModel):
    id: str = Field(description="步骤的唯一 ID，如 'step_1'")
    action_type: str = Field(description="执行技能名称")
    description: str = Field(description="该步骤执行逻辑的自然语言描述")
    inputs: List[str] = Field(description="该步骤使用的输入变量键名列表")
    outputs: List[str] = Field(description="该步骤产生的输出变量键名列表")


class WorkflowBlueprint(BaseModel):
    workflow_name: str = Field(description="工作流的大驼峰命名，如 'News_Crawler_Workflow'")
    description: str = Field(description="该流旨在解决的业务目标的一句话描述")
    estimated_steps: int = Field(description="主流程估计的步骤总数")
    should_split: bool = Field(description="逻辑过于复杂需要拆分为主副结构时设为 true")
    inputs: List[str] = Field(description="整个工作流对外暴露的入参列表")
    outputs: List[str] = Field(description="整个工作流最终产生的核心出参列表")
    sub_workflows: List[SubWorkflowBlueprint] = Field(
        default_factory=list, description="需要拆分的子工作流蓝图列表"
    )
    handoff_contracts: str = Field(description="主子工作流之间上下文变量的契约和约定")
    main_flow_steps: List[StepBlueprint] = Field(description="主工作流内部串联的执行步骤顺序")


# ── 技能实现 ──────────────────────────────────────────────────────────────

class LLMPlannerCall(LLMAgentSpec):
    """Planner 技能：解构用户需求，生成工作流拆解蓝图（返回 dict）。

    核心变更：返回 ``workflow_blueprint`` 为 Python dict（via model_dump()），
    而非 JSON 字符串（via model_dump_json()）。下游 Generator 直接使用 dict，
    无需二次解析。
    """

    name = "llm_planner_call"
    description = "解构用户需求为工作流蓝图（WorkflowBlueprint dict）"
    when_to_use = "有用户需求文本且需要宏观架构解构时"
    do_not_use_when = "蓝图已存在，或不需要工作流拆分时"
    idempotency = IdempotencyLevel.L2
    system_prompt_path = "planner_system_v1.md"
    default_temperature = 0.2

    def __init__(self) -> None:
        super().__init__()
        try:
            self._structured_llm = self._get_structured_llm(WorkflowBlueprint)
        except Exception as e:
            logger.error("❌ Planner LLM 初始化失败: %s", e)
            self._structured_llm = None

    @staticmethod
    def _build_skill_manifest(registered_skills: list[str]) -> str:
        if not registered_skills:
            return "- (empty)"
        return "\n".join(f"- {name}" for name in registered_skills)

    @staticmethod
    def _normalize_action_type(action_type: str, registered_skills: list[str]) -> tuple[str, str]:
        if not registered_skills:
            return action_type, ""
        clean = str(action_type or "").strip()
        if clean in registered_skills:
            return clean, ""
        matches = get_close_matches(clean, registered_skills, n=1, cutoff=0.72)
        if matches:
            return matches[0], "fuzzy_match"
        return clean, ""

    async def execute_step(self, step: dict, context: dict) -> dict:
        if not self._structured_llm:
            raise ValueError("Planner 的 LLM 客户端未成功初始化，无法执行。")

        requirement = context.get("requirement") or context.get("user_request")
        registered_skills: list[str] = context.get("registered_skills") or []
        if not requirement:
            logger.warning("⚠️ 未在上下文中找到 'requirement' 或 'user_request'。")
            requirement = "没有任何具体需求，请生成一个打招呼的工作流。"

        system_prompt = self._load_system_prompt()
        skill_manifest = self._build_skill_manifest(registered_skills)
        prompt = (
            f"{system_prompt}\n\n"
            f"━━━━━━━━━━━━━━ 当前可用技能清单（action_type 只能从此列表选择） ━━━━━━━━━━━━━━\n"
            f"{skill_manifest}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"━━━━━━━━━━━━━━ 用户原始工作流需求 ━━━━━━━━━━━━━━\n"
            f"{requirement}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        logger.info("🧠 [Planner] 正在解构宏观架构，调用 LLM 结构化输出...")

        try:
            blueprint: WorkflowBlueprint = await self._structured_llm.ainvoke(prompt)
        except Exception as e:
            logger.error("🔴 Planner 生成蓝图失败: %s", repr(e))
            raise

        action_audits: list[dict] = []
        planner_defects: list[dict] = []
        if registered_skills:
            for idx, step_spec in enumerate(blueprint.main_flow_steps, start=1):
                original = str(step_spec.action_type or "").strip()
                resolved, reason = self._normalize_action_type(original, registered_skills)
                if resolved in registered_skills and resolved != original:
                    step_spec.action_type = resolved
                    action_audits.append(
                        {
                            "step_id": idx,
                            "original_action_type": original,
                            "resolved_action_type": resolved,
                            "reason": reason,
                        }
                    )
                elif resolved not in registered_skills:
                    planner_defects.append(
                        {
                            "location": f"planner:step:{idx}",
                            "type": "LOGIC_ERROR",
                            "code": "WF_UNKNOWN_ACTIONS",
                            "fix_category": "model-fixable",
                            "reason": f"Planner 生成了未注册 action_type: {original}",
                            "suggestion": "请将 action_type 约束为 registered_skills 白名单中的值。",
                        }
                    )

        logger.info("✅ Planner 解构完成，预计主步骤数: %d", blueprint.estimated_steps)

        # 返回 dict 而非 JSON 字符串（核心变更）
        return {
            "workflow_blueprint": blueprint.model_dump(),
            "planner_action_audit": action_audits,
            "planner_validation_defects": planner_defects,
        }
