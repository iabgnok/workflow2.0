# execution_observer.py（新增，从 Runner 拆出）

## 一、为什么新增这个文件

context 压力采样当前分散在 Runner 主循环的多个点（run_start、step_before、step_after），最终通过 _flush_context_pressure_stats 写入 StateStore。这是纯 telemetry 逻辑，和执行控制流完全正交，而且未来可能需要扩展（加 step 耗时、LLM token 消耗等），应该有独立的扩展点。拆出后 Runner 不再感知任何观测细节。

## 二、ExecutionObserver 设计

同样采用带默认空实现的基类，DefaultExecutionObserver 是实现压力采样的默认版本，Runner.__init__ 里创建 DefaultExecutionObserver 实例注入，或者通过构造参数注入。
方法列表：

on_run_start(run_id: str, workflow_name: str, context: dict) -> None：记录初始压力。
on_step_start(run_id: str, step_id: int, context: dict) -> None：步骤执行前采样。
on_step_end(run_id: str, step_id: int, output: dict, context: dict) -> None：步骤执行后采样。
async flush(run_id: str, state_store) -> None：将统计数据写入 StateStore 的 run_meta，在 run 完成或失败时调用。

DefaultExecutionObserver 内部维护 _stats: dict（对应现有的 _context_pressure_stats），逻辑和现有实现完全相同，只是搬移到新文件里。依赖 ContextManager 做实际的压力估算（注入）。
当前 context 压力"只观测不行动"的问题：soft reset 和 hard reset 的实际闭环逻辑不在 Observer 里，Observer 只采样记录。真正的 reset 行为属于 ContextManager（infra/ 层），需要 Observer 在检测到 level >= 2 时通知 ContextManager 执行相应操作。Observer 和 ContextManager 的协作关系是：Observer 采样 → 超阈值时通知 ContextManager → ContextManager 执行裁剪/handoff。这个通知机制的具体实现 [待定：Observer 直接持有 ContextManager 引用并调用，还是通过回调/事件机制解耦]