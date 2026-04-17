"""LLMPromptCall 技能：执行自由文本 LLM 调用。

核心变更（design.md）：
  - 删除 Mock 模式：LLM 客户端初始化失败则直接抛出，不注册
  - 统一 execute_step 接口（弃用 execute(text, context) 旧式调用）
  - 继承 LLMAgentSpec
"""
from __future__ import annotations

import logging
import re

from agent.skills.base import IdempotencyLevel, LLMAgentSpec

logger = logging.getLogger(__name__)


class LLMPromptCall(LLMAgentSpec):
    """LLM 自由文本调用技能。

    从步骤内容中提取 ```prompt 代码块，发送给 LLM 并返回文本输出。
    不包含 Mock 模式——客户端初始化失败时直接抛出，不应被注册。
    """

    name = "llm_prompt_call"
    description = "从步骤内容提取 prompt 代码块，调用 LLM 并返回文本响应"
    when_to_use = "需要自由文本 LLM 调用，步骤内容包含 ```prompt 代码块时"
    do_not_use_when = "需要结构化输出时（请使用 Generator/Evaluator/Planner）"
    idempotency = IdempotencyLevel.L2
    system_prompt_path = ""  # 本技能不使用独立的系统 Prompt 文件
    default_temperature = 0.2

    def __init__(self) -> None:
        super().__init__()
        # 注意：没有 try/except——初始化失败则直接抛出，技能不应被注册
        from agent.infra.llm_factory import build_chat_model
        self._client = build_chat_model(temperature=self.default_temperature)

    async def execute_step(self, step: dict, context: dict) -> dict:
        """从步骤内容中提取 ```prompt 代码块并调用 LLM。

        变量替换由 StepExecutor 在调用前已完成，step['content'] 是替换后的文本。
        """
        content = step.get("content", "")
        prompt_match = re.search(r"```prompt\n(.*?)\n```", content, re.DOTALL)
        if not prompt_match:
            logger.warning("⚠️ LLMPromptCall 未找到 ```prompt 代码块，跳过执行。")
            return {}

        prompt = prompt_match.group(1).strip()

        logger.info("🤖 [LLMPromptCall] 正在调用 LLM...")
        try:
            response = await self._client.ainvoke(prompt)
            output = getattr(response, "content", None)
            if output is None:
                output = str(response)
            return {"llm_output": output}
        except Exception as e:
            logger.error("❌ 调用 LLM API 时发生错误: %s", e)
            raise
