"""条件求值器：simpleeval 沙箱，返回 (should_skip, reason) 元组。"""
from __future__ import annotations

import logging

from simpleeval import InvalidExpression, NameNotDefined, simple_eval

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """无状态条件求值器，可直接实例化复用。"""

    def eval(self, condition: str | None, context: dict) -> tuple[bool, str]:
        """
        求值 condition 表达式。

        Returns:
            (should_skip, reason)
            - (False, "")          条件为 None 或求值为 truthy
            - (True,  reason)      条件 falsy / 变量未就绪 / 表达式非法时按约定跳过
              注意：InvalidExpression 时 *不* 跳过，默认执行（see design.md Decision 4）
        """
        if condition is None:
            return (False, "")

        try:
            passed = simple_eval(condition, names=context)
            if not passed:
                return (True, f"条件不满足: {condition}")
            return (False, "")
        except NameNotDefined as exc:
            return (True, f"条件变量未就绪: {exc}")
        except (InvalidExpression, SyntaxError) as exc:
            logger.warning("⚠️ 条件表达式非法 [%s]: %s，默认执行。", condition, exc)
            return (False, "")
