# infra/ 目录

这个目录下的六个文件全部是从 engine/ 搬移来的，搬移本身已在 engine 分析阶段说明理由。这里只补充没有在 engine 分析阶段覆盖到的实现细节，以及新增的 LLMClientRegistry。
详细的设计说明见 engine/分析里对应的六个文件:variable_mapper_move.md、skill_registry_move.md、error_policy_change.md、llm_factory_move.md、state_store_move.md、workflow_registry_move.md、context_manager_move.md。

nfra/ 搬移文件汇总：state_store.py（新增 AbstractStateStore 接口 + SQLiteStateStore 重命名）、llm_factory.py（新增 LLMClientRegistry 单例）、skill_registry.py（递归扫描 + build_skill_manifest）、workflow_registry.py（新增 register_workflow_model 主路径）、context_manager.py（新增 perform_soft_reset / perform_hard_reset 闭环）、variable_mapper.py（新增 VariableMappingError，map_outputs 改返回值）、error_policy.py（execute_with_policy 移入 StepExecutor，保留工具函数）

跳转：

- [engine/variable_mapper_move.md](/design/change/agent/engine/variable_mapper_move.md)
- [engine/skill_registry_move.md](/design/change/agent/engine/skill_registry_move.md)
- [engine/error_policy_move.md](/design/change/agent/engine/error_policy_move.md)
- [engine/llm_factory_move.md](/design/change/agent/engine/llm_factory_move.md)
- [engine/state_store_move.md](/design/change/agent/engine/state_store_move.md)
- [engine/workflow_registry_move.md](/design/change/agent/engine/workflow_registry_move.md)
- [engine/context_manager_move.md](/design/change/agent/engine/context_manager_move.md)