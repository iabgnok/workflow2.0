"""上下文管理器。

提供上下文压力评估、切换触发判断和 Handoff Artifact 构建工具。
新增 perform_soft_reset() 和 perform_hard_reset() 方法，
用于在上下文压力过高时显式清理聊天历史。
"""
from __future__ import annotations

from typing import Any


class ContextManager:
    """上下文压力管理与切换工具。

    职责：
    1. 轻量级 token 估算（基于字符数启发式）。
    2. 压力等级判断（1=正常, 2=软重置, 3=硬重置）。
    3. 执行软/硬重置：清理 chat_history 等运行时字段。
    4. 构建切换 Artifact（用于下一轮 agent 接棒）。
    """

    def __init__(
        self,
        soft_ratio: float = 0.60,
        hard_ratio: float = 0.80,
    ) -> None:
        if not (0 < soft_ratio < hard_ratio < 1):
            raise ValueError("soft_ratio and hard_ratio must satisfy 0 < soft < hard < 1")
        self.soft_ratio = soft_ratio
        self.hard_ratio = hard_ratio

    # ── Token 估算 ────────────────────────────────────────────────────────────

    def estimate_tokens(self, payload: Any) -> int:
        """轻量级字符数启发式 token 估算。"""
        if payload is None:
            return 0
        if isinstance(payload, str):
            return max(1, len(payload) // 4)
        if isinstance(payload, (int, float, bool)):
            return 1
        if isinstance(payload, dict):
            return sum(self.estimate_tokens(k) + self.estimate_tokens(v) for k, v in payload.items())
        if isinstance(payload, (list, tuple, set)):
            return sum(self.estimate_tokens(v) for v in payload)
        return max(1, len(str(payload)) // 4)

    # ── 压力评估 ──────────────────────────────────────────────────────────────

    def context_pressure_ratio(self, context: dict[str, Any], context_window_tokens: int) -> float:
        if context_window_tokens <= 0:
            raise ValueError("context_window_tokens must be > 0")
        estimated = self.estimate_tokens(context)
        return estimated / float(context_window_tokens)

    def pressure_level(self, context: dict[str, Any], context_window_tokens: int) -> int:
        """返回压力等级：1（正常）、2（软重置）、3（硬重置）。"""
        ratio = self.context_pressure_ratio(context, context_window_tokens)
        if ratio >= self.hard_ratio:
            return 3
        if ratio >= self.soft_ratio:
            return 2
        return 1

    def should_reset(self, context: dict[str, Any], context_window_tokens: int) -> bool:
        return self.pressure_level(context, context_window_tokens) >= 2

    # ── 重置操作（新增）──────────────────────────────────────────────────────

    @staticmethod
    def perform_soft_reset(context: dict[str, Any], max_history: int) -> None:
        """软重置：将 chat_history 裁剪为最近 max_history 条记录（原地修改）。

        适用于上下文压力达到软阈值时，保留最近对话以维持短期记忆。

        Args:
            context:     工作流运行时上下文（原地修改）。
            max_history: 保留的最大历史条数。
        """
        history = context.get("chat_history")
        if isinstance(history, list) and len(history) > max_history:
            context["chat_history"] = history[-max_history:]

    @staticmethod
    def perform_hard_reset(context: dict[str, Any]) -> None:
        """硬重置：清空 chat_history（原地修改）。

        适用于上下文压力达到硬阈值时，彻底释放对话历史占用的 token。

        Args:
            context: 工作流运行时上下文（原地修改）。
        """
        context["chat_history"] = []

    # ── Handoff Artifact 构建 ──────────────────────────────────────────────────

    async def build_handoff_artifact(
        self,
        run_id: str,
        state_store,
        next_objective: str | None = None,
    ) -> dict[str, Any]:
        """从持久化运行状态构建切换 Artifact。

        Args:
            run_id:          运行 ID。
            state_store:     AbstractStateStore 实例。
            next_objective:  下一轮目标描述（可选）。

        Returns:
            结构化切换 Artifact 字典。
        """
        if not run_id:
            raise ValueError("run_id is required")

        run_state = await state_store.load_run_state(run_id) or {}
        run_meta = await state_store.load_run_meta(run_id) or {}
        latest_step = await state_store.load_latest_step_state(run_id, status="success")

        state_context = dict(run_state.get("context") or {})
        meta_context = dict(run_state.get("meta_context") or {})
        merged_context = {**state_context, **meta_context}

        default_objective = "基于 champion_draft 与 last_feedback 进行下一轮修复"
        return {
            "run_id": run_id,
            "workflow_name": run_state.get("workflow_name"),
            "run_status": run_state.get("status"),
            "current_step_id": run_state.get("current_step_id"),
            "var_snapshot": merged_context,
            "champion_draft": run_meta.get("champion_json"),
            "last_feedback": run_meta.get("last_feedback"),
            "registration_audit": run_meta.get("registration_audit"),
            "context_pressure": run_meta.get("context_pressure"),
            "latest_step": latest_step,
            "next_objective": next_objective or default_objective,
        }
