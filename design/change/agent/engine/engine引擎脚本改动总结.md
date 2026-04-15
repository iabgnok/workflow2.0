# Engine 引擎脚本改动总结

新增文件：step_executor.py、condition_evaluator.py、resume_strategy.py、execution_hooks.py（含 StepHookResult）、execution_observer.py

移入 infra/：context_manager.py、skill_registry.py（含 SkillNotFoundError）、workflow_registry.py、variable_mapper.py、llm_factory.py（扩展 LLMClientRegistry）、state_store.py（抽象接口 + 重命名 SQLiteStateStore）

保留在 engine/：runner.py（大幅精简）、parser.py（职责收窄）

消失：step_validator.py（吸收进 StepExecutor）

error_policy.py 的最终归属 [待定：engine/ 还是 infra/，倾向于 infra/，因为它是"外部行为策略"而非控制流逻辑，但和 StepExecutor 关系紧密，可放 engine/]