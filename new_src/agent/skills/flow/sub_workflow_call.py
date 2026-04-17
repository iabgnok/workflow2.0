"""SubWorkflowCall 技能：调用子工作流并映射输入输出变量。

核心变更（spec）：
  - 从 agent.infra.variable_mapper 导入（修复依赖方向：skill → infra，非 skill → engine）
  - 增强输入变量校验：子流程必须变量缺失时抛出 VariableMappingError
"""
from __future__ import annotations

import logging

from agent.infra.variable_mapper import VariableMappingError, VariableMapper
from agent.skills.base import FlowSkillSpec, IdempotencyLevel

logger = logging.getLogger(__name__)


class SubWorkflowCall(FlowSkillSpec):
    """子工作流调用技能。

    读取步骤的 workflow 字段获取子流程路径，
    按 inputs/outputs 映射在父子上下文间传递变量。
    在创建子 Runner 前校验所有必须输入变量是否存在于父 context。
    """

    name = "sub_workflow_call"
    description = "调用子工作流，完成父子上下文变量隔离与映射"
    when_to_use = "主工作流需要委托一段独立逻辑给子工作流时"
    do_not_use_when = "逻辑简单，不需要子流程隔离时"
    idempotency = IdempotencyLevel.L2

    async def execute_step(self, step: dict, context: dict) -> dict:
        """执行子工作流调用。

        Args:
            step:    已解析步骤，需包含 ``workflow``、``inputs``、``outputs`` 字段。
            context: 父工作流上下文。

        Raises:
            ValueError: 缺少 workflow 路径时。
            VariableMappingError: 必须输入变量在父 context 中不存在时。
        """
        workflow_path: str | None = step.get("workflow")
        if not workflow_path:
            raise ValueError(
                "SubWorkflowCall: 缺少必须参数 'workflow'（请在步骤中声明 **Workflow**）。"
            )

        input_mapping: dict[str, str] = step.get("inputs") or {}
        output_mapping: dict[str, str] = step.get("outputs") or {}

        return await self._run_sub_workflow(workflow_path, input_mapping, output_mapping, context)

    async def _run_sub_workflow(
        self,
        workflow_path: str,
        input_mapping: dict[str, str],
        output_mapping: dict[str, str],
        context: dict,
    ) -> dict:
        # 1. 归一化并校验输入变量（支持 "foo?" 可选输入）
        normalized_input_mapping: dict[str, str] = {}
        required_keys: list[str] = []
        for child_key, parent_path in (input_mapping or {}).items():
            is_optional = child_key.endswith("?")
            normalized_child_key = child_key[:-1] if is_optional else child_key
            normalized_parent_path = (
                parent_path[:-1] if isinstance(parent_path, str) and parent_path.endswith("?") else parent_path
            )
            normalized_input_mapping[normalized_child_key] = normalized_parent_path
            if not is_optional:
                required_keys.append(normalized_child_key)

        child_context = VariableMapper.map_inputs(
            context, normalized_input_mapping, required_keys=required_keys
        )

        logger.info(
            "🔄 [SubWorkflow] 启动子工作流 '%s'，初始上下文变量: %s",
            workflow_path,
            list(child_context.keys()),
        )

        # 2. 本地导入 Runner，避免循环依赖
        from agent.engine.runner import Runner  # type: ignore[import]

        sub_runner = Runner(filepath=workflow_path, initial_context=child_context)

        # 3. 执行子工作流
        result = await sub_runner.run()
        if result.get("status") != "success":
            raise RuntimeError(
                f"SubWorkflowCall: 子工作流执行失败，状态: {result.get('status')}"
            )

        child_final_context = result.get("context", {})

        # 4. 按 output_mapping 写回父 context（sub_ 前缀约定由 VariableMapper output 阶段处理）
        VariableMapper.map_outputs(child_final_context, context, output_mapping)
        logger.info("🔄 [SubWorkflow] 子工作流执行完毕，已映射输出变量。")

        # 收集实际写回父 context 的变量
        mapped_results: dict = {}
        for parent_path, child_path in output_mapping.items():
            val = VariableMapper._get_nested_value(child_final_context, child_path)
            if val is not None:
                mapped_results[parent_path] = val

        return {
            "__sub_workflow_status__": "success",
            "__sub_run_id__": result.get("run_id"),
            **mapped_results,
        }
