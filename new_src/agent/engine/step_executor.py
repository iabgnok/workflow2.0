"""单步执行器：变量注入 → 前置断言 → 技能查找 → execute_with_policy → 后置断言。

职责边界（见 design.md Decision 1）：
- 不做条件求值（Runner 主循环负责）
- 不做状态持久化（Runner 主循环负责）
- 不做 on_reject 路由（Runner 主循环负责）
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class StepExecutor:
    """
    依赖注入风格：所有外部依赖通过构造函数传入，便于单元测试 mock。

    Args:
        skill_registry:      拥有 get_all() / get(name) 方法的技能注册表。
        protocol_service:    拥有 validate_runtime_step_inputs/outputs 方法的协议服务。
        replace_variables:   WorkflowParser.replace_variables 静态方法（str, dict -> str）。
        execute_with_policy: error_policy.execute_with_policy 函数。
    """

    def __init__(
        self,
        skill_registry,
        protocol_service,
        replace_variables: Callable[[str, dict], str],
        execute_with_policy: Callable[..., Awaitable[Any]],
    ) -> None:
        self._registry = skill_registry
        self._protocol = protocol_service
        self._replace_variables = replace_variables
        self._execute_with_policy = execute_with_policy

    async def execute(self, step: dict, context: dict) -> dict:
        """执行单步并返回 output dict。可抛出 SkillNotFoundError 或执行异常。"""

        # 1. 变量注入
        text_context = self._replace_variables(step.get("content", ""), context)

        # 2. 前置断言
        self._protocol.validate_runtime_step_inputs(step, context)

        # 3. 技能查找
        skill_name = step["action"]
        skill = self._lookup_skill(skill_name)

        # 4. execute_with_policy
        if hasattr(skill, "execute_step"):
            step_copy = dict(step)
            step_copy["content"] = text_context
            output = await self._execute_with_policy(
                skill_name, skill.execute_step, step_copy, context
            )
        else:
            output = await self._execute_with_policy(
                skill_name, skill.execute, text_context, context
            )

        output = output or {}
        logger.info("✅ 技能 %s 执行完毕，输出变量: %s", skill_name, list(output.keys()))

        # 5. 后置断言
        self._protocol.validate_runtime_step_outputs(step, output, context)

        return output

    def _lookup_skill(self, skill_name: str):
        """从注册表查找技能；未找到则抛出 SkillNotFoundError。"""
        # 延迟导入，避免循环依赖；异常类型统一来自 infra 层。
        try:
            from agent.infra.skill_registry import SkillNotFoundError
        except ImportError:
            class SkillNotFoundError(Exception):  # type: ignore[no-redef]
                pass

        skills = self._registry.get_all()
        if skill_name in skills:
            return skills[skill_name]
        try:
            return self._registry.get(skill_name)
        except Exception:
            raise SkillNotFoundError(f"未注册的技能: '{skill_name}'")
