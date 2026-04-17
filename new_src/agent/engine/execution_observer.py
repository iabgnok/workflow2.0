"""执行观测器：上下文压力采样与遥测（替代 Runner._observe_context_pressure）。"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionObserver:
    """抽象基类；子类实现具体采样逻辑。"""

    async def on_step_start(self, step_id: int, context: dict) -> None:
        pass

    async def on_step_end(self, step_id: int, context: dict) -> None:
        pass

    async def flush(self, run_id: str, context: dict, state_store: Any) -> None:
        pass


class DefaultExecutionObserver(ExecutionObserver):
    """
    对每个步骤的前后边界采样上下文压力比率，并在工作流结束时将统计持久化。

    Args:
        context_manager:      拥有 context_pressure_ratio / pressure_level 方法的对象。
        context_window_tokens: 上下文窗口大小（token 数）。
    """

    def __init__(self, context_manager: Any, context_window_tokens: int) -> None:
        self._cm = context_manager
        self._window = context_window_tokens
        self._stats: dict | None = None

    async def on_step_start(self, step_id: int, context: dict) -> None:
        self._sample(f"step_{step_id}_before", context)

    async def on_step_end(self, step_id: int, context: dict) -> None:
        self._sample(f"step_{step_id}_after", context)

    def _sample(self, phase: str, context: dict) -> None:
        try:
            ratio = self._cm.context_pressure_ratio(context, self._window)
            level = self._cm.pressure_level(context, self._window)
        except Exception as exc:
            logger.debug("[Context Pressure] 观测失败，phase=%s: %s", phase, exc)
            return

        if self._stats is None:
            self._stats = {
                "window_tokens": self._window,
                "samples": 0,
                "alerts": 0,
                "max_ratio": 0.0,
                "max_level": 1,
                "last_ratio": 0.0,
                "last_level": 1,
                "last_phase": "",
            }

        s = self._stats
        ratio_f = float(ratio)
        s["samples"] += 1
        s["max_ratio"] = max(float(s["max_ratio"]), ratio_f)
        s["max_level"] = max(int(s["max_level"]), int(level))
        s["last_ratio"] = ratio_f
        s["last_level"] = int(level)
        s["last_phase"] = phase
        if level >= 2:
            s["alerts"] += 1

        if level >= 3:
            logger.warning(
                "🧭 [Context Pressure] phase=%s level=%s ratio=%.2f (window=%s)",
                phase, level, ratio_f, self._window,
            )
        elif level == 2:
            logger.info(
                "🧭 [Context Pressure] phase=%s level=%s ratio=%.2f (window=%s)",
                phase, level, ratio_f, self._window,
            )
        else:
            logger.debug(
                "[Context Pressure] phase=%s level=%s ratio=%.2f",
                phase, level, ratio_f,
            )

    async def flush(self, run_id: str, context: dict, state_store: Any) -> None:
        """将统计数据写入 context 并持久化到 state_store。"""
        if not run_id or not self._stats or int(self._stats.get("samples", 0)) <= 0:
            return

        context["context_pressure"] = self._stats
        handoff = context.get("handoff_artifact")
        if isinstance(handoff, dict):
            handoff["context_pressure"] = self._stats
        else:
            context["handoff_artifact"] = {"context_pressure": self._stats}

        try:
            await state_store.save_run_meta(run_id, context_pressure=self._stats)
        except Exception as exc:
            logger.debug("[Context Pressure] 持久化失败，run_id=%s: %s", run_id, exc)
