"""错误策略与三级幂等性框架。

定义技能执行的错误重试策略：
- L0（强幂等）：无副作用，可安全自动重试。
- L1（条件幂等）：需检查前置条件后可重试。
- L2（非幂等）：不可自动重试，每次执行都产生新副作用。

依赖 agent.infra.skill_registry.SkillNotFoundError（infra 内部依赖，符合分层规则）。
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from enum import Enum

from agent.infra.skill_registry import SkillNotFoundError

logger = logging.getLogger(__name__)


# ── 枚举定义 ──────────────────────────────────────────────────────────────────

class IdempotencyLevel(Enum):
    L0 = "L0"  # 强幂等：无副作用，可安全自动重试（读文件、纯查询计算）
    L1 = "L1"  # 条件幂等：执行前需检查前置条件/guard，安全后可重试（写文件、Git 提交）
    L2 = "L2"  # 非幂等：不可自动重试，每次执行产生新副作用（发邮件、删除文件）


class FailureAction(Enum):
    RETRY    = "retry"      # 继续重试（内部状态，用于循环内）
    CONFIRM  = "confirm"    # 触发人工确认 / 暂停执行
    ROLLBACK = "rollback"   # 执行回退流
    SKIP     = "skip"       # 忽略错误跳过该步骤


# ── 策略数据类 ────────────────────────────────────────────────────────────────

@dataclass
class ErrorPolicy:
    max_retries: int = 3
    backoff_base: float = 2.0
    action_on_exhaust: FailureAction = FailureAction.CONFIRM


# ── 默认策略表 ────────────────────────────────────────────────────────────────

DEFAULT_POLICIES: dict[str, ErrorPolicy] = {
    "file_reader":         ErrorPolicy(3, 2.0, FailureAction.CONFIRM),
    "file_writer":         ErrorPolicy(2, 2.0, FailureAction.CONFIRM),
    "llm_prompt_call":     ErrorPolicy(2, 3.0, FailureAction.CONFIRM),
    "llm_planner_call":    ErrorPolicy(2, 2.0, FailureAction.CONFIRM),
    "llm_generator_call":  ErrorPolicy(2, 2.0, FailureAction.CONFIRM),
    "llm_evaluator_call":  ErrorPolicy(2, 2.0, FailureAction.CONFIRM),
    "shell_executor":      ErrorPolicy(0, 0.0, FailureAction.CONFIRM),  # L2，不自动重试
    "DANGER":              ErrorPolicy(0, 0.0, FailureAction.ROLLBACK),
}

# 技能硬编码的幂等性等级
SKILL_IDEMPOTENCY: dict[str, IdempotencyLevel] = {
    "file_reader":        IdempotencyLevel.L0,
    "file_writer":        IdempotencyLevel.L1,
    "llm_prompt_call":    IdempotencyLevel.L0,
    "llm_planner_call":   IdempotencyLevel.L0,
    "llm_generator_call": IdempotencyLevel.L0,
    "llm_evaluator_call": IdempotencyLevel.L0,
    "shell_executor":     IdempotencyLevel.L2,
}


# ── 策略解析 ──────────────────────────────────────────────────────────────────

def resolve_policy(skill_name: str, step_metadata: dict | None = None) -> ErrorPolicy:
    """根据技能名解析合并后的错误重试策略。"""
    return DEFAULT_POLICIES.get(skill_name, ErrorPolicy(0, 0.0, FailureAction.CONFIRM))


# ── 带策略保护的执行器 ────────────────────────────────────────────────────────

async def execute_with_policy(skill_name: str, execute_func, *args, **kwargs):
    """基于 tenacity 的带 Error Policy 保护框架的技能执行器。

    - L0/L1：依据 max_retries 进行指数退避重试。
    - L2：拦截自动重试，直接失败。
    """
    from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

    policy = resolve_policy(skill_name)
    level = SKILL_IDEMPOTENCY.get(skill_name, IdempotencyLevel.L2)
    max_retries = policy.max_retries if level in (IdempotencyLevel.L0, IdempotencyLevel.L1) else 0

    if max_retries == 0:
        try:
            if inspect.iscoroutinefunction(execute_func):
                return await execute_func(*args, **kwargs)
            else:
                return await asyncio.to_thread(execute_func, *args, **kwargs)
        except SkillNotFoundError:
            raise
        except Exception as e:
            logger.error("❌ 技能 %s (%s) 执行失败，不允许重试: %s", skill_name, level.value, e)
            raise Exception(
                f"[{policy.action_on_exhaust.value.upper()}] Skill {skill_name} failed: {e}"
            )

    # L0/L1：启用 tenacity 重试
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_retries + 1),
            wait=wait_exponential(multiplier=policy.backoff_base, min=1, max=30),
            reraise=True,
        ):
            with attempt:
                if attempt.retry_state.attempt_number > 1:
                    logger.warning(
                        "⚠️ 技能 %s 进行第 %d/%d 次重试...",
                        skill_name,
                        attempt.retry_state.attempt_number - 1,
                        max_retries,
                    )
                if inspect.iscoroutinefunction(execute_func):
                    return await execute_func(*args, **kwargs)
                else:
                    return await asyncio.to_thread(execute_func, *args, **kwargs)
    except SkillNotFoundError:
        raise
    except Exception as e:
        logger.error(
            "🚫 技能 %s 重试耗尽（已尝试 %d 次），触发耗尽策略: %s",
            skill_name, max_retries, policy.action_on_exhaust.value,
        )
        raise Exception(
            f"[{policy.action_on_exhaust.value.upper()}] Skill {skill_name} "
            f"failed after {max_retries} retries. Cause: {e}"
        )
