"""协议层内部共用工具函数。

这些函数是协议层的内部工具，专门处理工作流变量名的归一化和元数据输入提取。
不对协议层外部暴露（ZERO 外部依赖）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.engine.protocol.models import WorkflowModel


def normalize_var_name(value: str) -> str:
    """归一化变量名：去除空白、反引号、模板语法和可选标记。

    处理顺序：
    1. 去除首尾空白
    2. 去除反引号
    3. 提取 {{...}} 模板内部名称
    4. 去除末尾 `?` 可选标记

    Examples:
        normalize_var_name("{{ user_input? }}")  -> "user_input"
        normalize_var_name("  `file_path`  ")    -> "file_path"
    """
    text = (value or "").strip().strip("`").strip()
    if text.startswith("{{") and text.endswith("}}"):
        text = text[2:-2].strip()
    if text.endswith("?"):
        text = text[:-1]
    return text


def extract_metadata_inputs(workflow: WorkflowModel) -> set[str]:
    """从工作流元数据中提取所有已声明的输入变量名（归一化后）。

    Example:
        workflow.metadata.inputs = ["requirement", "output_path?"]
        -> {"requirement", "output_path"}
    """
    inputs = workflow.metadata.inputs
    if isinstance(inputs, dict):
        return {normalize_var_name(k) for k in inputs.keys() if normalize_var_name(k)}
    return {normalize_var_name(x) for x in inputs if normalize_var_name(x)}


def is_optional_var(value: str) -> bool:
    """判断变量名是否为可选变量（原始值末尾含 `?`）。

    Examples:
        is_optional_var("prev_defects?")  -> True
        is_optional_var("requirement")    -> False
    """
    return str(value or "").strip().endswith("?")
