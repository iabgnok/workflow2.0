"""执行钩子协议（五条约定）：
1. async 方法
2. 无有意义返回值（on_step_before 除外）
3. 异常隔离（钩子内部异常不传播到 Runner）
4. FIFO 执行顺序（组合时）
5. context 只读
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StepHookResult:
    """on_step_before 的返回值；skip=True 时 Runner 跳过该步骤。"""
    skip: bool = False


class ExecutionHooks:
    """基类：所有方法均为空实现，供子类覆盖。"""

    async def on_run_start(self, run_id: str, context: dict) -> None:
        pass

    async def on_step_before(self, step: dict, context: dict) -> StepHookResult:
        return StepHookResult()

    async def on_step_after(self, step: dict, output: dict, context: dict) -> None:
        pass

    async def on_run_end(self, run_id: str, context: dict) -> None:
        pass
