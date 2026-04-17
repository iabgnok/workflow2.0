"""VariableMapper：父子工作流间的变量映射工具。

这是 infra-layer-extract 变更将扩展的基础模块；
SubWorkflowCall 显式从 agent.infra.variable_mapper 导入，以确保正确的依赖方向
（skill 层 → infra 层，而非 skill 层 → engine 层）。
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class VariableMappingError(ValueError):
    """输入变量映射失败时抛出（如父 context 中找不到必须变量）。"""


class VariableMapper:
    """在父子工作流之间传递和映射上下文变量，确保变量隔离。"""

    @staticmethod
    def _get_nested_value(context: Dict[str, Any], path: str) -> Any:
        """根据路径（如 'user.profile.name'）从 context 中获取嵌套值。"""
        if not path:
            return None
        keys = path.split(".")
        current: Any = context
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    @staticmethod
    def _set_nested_value(context: Dict[str, Any], path: str, value: Any) -> None:
        """根据路径在 context 中设置嵌套值。"""
        if not path:
            return
        keys = path.split(".")
        current = context
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    @staticmethod
    def _safe_deepcopy(value: Any) -> Any:
        try:
            return copy.deepcopy(value)
        except Exception:
            logger.warning("⚠️ 变量深拷贝失败，回退为原值传递。")
            return value

    @classmethod
    def map_inputs(
        cls,
        parent_context: Dict[str, Any],
        input_mapping: Dict[str, str],
        *,
        required_keys: list[str] | None = None,
    ) -> Dict[str, Any]:
        """从父 context 提取变量，生成子工作流的初始 context。

        Args:
            parent_context: 父工作流上下文。
            input_mapping:  映射规则 {子变量名: 父变量路径}。
            required_keys:  必须存在于父 context 中的变量列表；缺失时抛出 VariableMappingError。

        Returns:
            子工作流初始 context。
        """
        # 必须变量校验（增强输入校验）
        if required_keys:
            for key in required_keys:
                parent_path = input_mapping.get(key, key)
                if cls._get_nested_value(parent_context, parent_path) is None:
                    raise VariableMappingError(
                        f"SubWorkflow 输入变量 '{key}' 在父 context 中不存在（路径: '{parent_path}'）"
                    )

        child_context: Dict[str, Any] = {}
        if not input_mapping:
            return child_context

        for child_key, parent_path in input_mapping.items():
            value = cls._get_nested_value(parent_context, parent_path)
            if value is not None:
                cls._set_nested_value(child_context, child_key, cls._safe_deepcopy(value))
            else:
                logger.warning(
                    "⚠️ 父 context 中未找到路径 '%s' 的值，映射到 '%s' 失败。",
                    parent_path,
                    child_key,
                )

        return child_context

    @classmethod
    def map_outputs(
        cls,
        child_context: Dict[str, Any],
        parent_context: Dict[str, Any],
        output_mapping: Dict[str, str],
    ) -> None:
        """从子 context 提取变量，写回父 context（原地修改）。"""
        if not output_mapping:
            return

        for parent_path, child_path in output_mapping.items():
            value = cls._get_nested_value(child_context, child_path)
            if value is not None:
                cls._set_nested_value(parent_context, parent_path, cls._safe_deepcopy(value))
            else:
                logger.warning(
                    "⚠️ 子 context 中未找到路径 '%s' 的值，映射回父路径 '%s' 失败。",
                    child_path,
                    parent_path,
                )
