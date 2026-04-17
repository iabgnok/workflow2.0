"""断点恢复策略：加载状态 → 注水上下文 → 确定起始步骤。"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ResumeStrategy:
    """无状态策略对象，可直接实例化复用。"""

    async def resume(self, run_id: str | None, state_store, context: dict) -> int:
        """
        根据 run_id 决定从哪一步开始执行，并将历史状态注水到 context。

        Returns:
            start_step_id (int)：从该 step id 开始执行（1-based）。
        """
        if run_id is None:
            return 1

        state = await state_store.load_run_state(run_id)
        if not state:
            logger.warning("⚠️ 未找到 run_id: %s 的状态记录，作为全新任务开始。", run_id)
            return 1

        logger.info("🔄 找到已存在状态的 run_id: %s，从中断处继续...", run_id)

        # 注水基础上下文
        context.update(state.get("context", {}))
        context.update(state.get("meta_context", {}))
        start_step_id: int = state.get("current_step_id", 1)

        # 注水最新成功步骤的完整快照（更精确）
        latest = await state_store.load_latest_step_state(run_id, status="success")
        if latest:
            context.update(latest.get("full_context", {}))
            context.update(latest.get("meta_full_context", {}))
            start_step_id = max(start_step_id, latest.get("step_id", 0) + 1)

        return start_step_id
