"""FileWriter 技能：将内容写入文件系统。

核心变更（spec）：
  - 删除手动变量替换（StepExecutor 已在调用前完成替换）
  - 自动创建父目录（不再要求目录预先存在）
"""
from __future__ import annotations

import logging
import os

from agent.skills.base import IdempotencyLevel, IOSkillSpec

logger = logging.getLogger(__name__)


class FileWriter(IOSkillSpec):
    """文件写入技能。

    接收 step['content'] 中的内容（已由 StepExecutor 完成变量替换），
    以及 context 中的 target_file 变量，写入文件并自动创建父目录。
    """

    name = "file_writer"
    description = "将内容写入指定路径的文件，自动创建父目录"
    when_to_use = "需要将文本内容持久化到文件时"
    do_not_use_when = "只需要读取文件时（请使用 file_reader）"
    idempotency = IdempotencyLevel.L1

    async def execute_step(self, step: dict, context: dict) -> dict:
        """将步骤内容写入目标文件。

        Args:
            step:    已解析的步骤元数据，``step['content']`` 是变量替换后的文本。
            context: 工作流上下文，持有 target_file 等变量。

        Returns:
            ``{"file_writer_status": "Success"}``
        """
        content = step.get("content", "")
        # 不做变量替换——StepExecutor 保证调用前已完成

        # 从 inputs 映射或 context 直接取目标路径
        inputs_mapping: dict[str, str] = step.get("inputs") or {}
        source_key = inputs_mapping.get("target_file", "target_file")
        file_path = context.get(source_key) or context.get("target_file", "output.txt")

        # 自动创建父目录
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("[FileWriter] 文件写入完成: %s (%d 字符)", file_path, len(content))
        return {"file_writer_status": "Success"}
