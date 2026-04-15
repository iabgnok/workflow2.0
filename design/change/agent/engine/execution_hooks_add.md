# execution_hooks.py（新增）

## 一、为什么新增这个文件

已在 Runner 分析里详细说明：Runner 当前通过 workflow_name == "Meta Main Workflow" 字符串判断激活业务逻辑，这是引擎耦合业务的最典型反例。ExecutionHooks 是解耦手段，定义接口契约，业务层实现，Runner 调用接口不知道实现细节。

## 二、ExecutionHooks 基类设计

这是一个 Protocol 类（typing.Protocol）或者带默认空实现的普通基类。倾向于带默认空实现的普通基类，原因：测试时不需要实现所有方法，只覆盖需要的；子类可以选择性 override。
所有方法都是 async，返回值除 on_step_before 外均为 None，不抛异常（即使业务逻辑失败，不应该中断主执行流）——内部 try/except 吞掉异常并打 error 日志。[待定：hook 失败时是否应该让 Runner 感知并决定是否继续，还是严格静默吞掉？当前倾向静默，因为 hook 是业务观测行为，不应干扰引擎主链路]
方法列表及说明：

- async on_run_start(run_id: str, context: dict) -> None：Runner 开始执行、断点续传恢复完毕后调用。ChampionTracker 在这里做 composite champion reuse 检查（_try_enable_composite_champion_reuse 的逻辑）。
- async on_step_before(run_id: str, step, context: dict) -> StepHookResult：每步条件求值通过后、实际执行前调用。返回 StepHookResult(skip: bool = False)，Runner 读取 skip 决定是否跳过本步。ChampionTracker 在这里做 champion replay 判断（_try_replay_champion_for_meta 的逻辑）。
- async on_step_after(run_id: str, step, output: dict, context: dict) -> None：每步执行成功、状态持久化完成后调用，在 on_reject 路由判断之前。ChampionTracker 在这里做 champion 更新（_update_champion 的逻辑）。
- async on_workflow_complete(run_id: str, context: dict) -> None：所有步骤完成后、最终状态持久化之前调用。ChampionTracker 在这里触发注册和回放（_register_if_meta_workflow + _attempt_generated_workflow_replay 的逻辑）。

StepHookResult 是一个简单的 dataclass，只有 skip: bool = False 一个字段，定义在同文件内。