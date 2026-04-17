"""FileReader 技能：从文件系统读取文件内容。

核心变更（spec）：
  - 从 step['inputs'] 映射中读取文件路径，而非直接从 context 获取
"""
from __future__ import annotations

import logging
import os

from agent.skills.base import IdempotencyLevel, IOSkillSpec

logger = logging.getLogger(__name__)


class FileReader(IOSkillSpec):
    """文件读取技能。

    通过 step['inputs'] 映射解析文件路径：
      step['inputs']['file_path'] 的值是 context 中持有路径的变量名。
    若映射中未声明 'file_path'，回退为直接从 context 读取 'file_path'。
    """

    name = "file_reader"
    description = "从指定路径读取文件内容，输出 file_content 变量"
    when_to_use = "需要读取本地文件内容时"
    do_not_use_when = "需要写入文件时（请使用 file_writer）"
    idempotency = IdempotencyLevel.L0

    async def execute_step(self, step: dict, context: dict) -> dict:
        """从 step['inputs'] 映射解析文件路径并读取文件。

        Args:
            step:    已解析的步骤元数据，``step['inputs']`` 为 dict[str, str]。
            context: 工作流上下文，持有实际的变量值。

        Returns:
            ``{"file_content": <文件内容字符串>}``
        """
        # 从 step['inputs'] 查找 file_path 对应的 context 变量名
        inputs_mapping: dict[str, str] = step.get("inputs") or {}
        source_key = inputs_mapping.get("file_path", "file_path")
        file_path = context.get(source_key)

        if not file_path:
            logger.error(
                "[FileReader] 未找到文件路径：inputs 映射 = %s，context 中无对应变量。",
                inputs_mapping,
            )
            return {}

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        logger.info("[FileReader] 正在读取文件: %s", file_path)
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        logger.info("[FileReader] 成功读取 %d 字符。", len(content))
        return {"file_content": content}
