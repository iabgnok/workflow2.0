# context_manager.py → 移入 infra/ 重构实现细节

## 一、文件搬移

context_manager.py 从 agent/engine/ 移入 agent/infra/，原因：它是基础设施层工具，不是引擎核心控制流的一部分。Runner 通过注入 ContextManager 实例使用它，依赖方向是 engine → infra，搬移后依赖方向不变。

## 二、estimate_tokens() 方法

保持现有的基于字符数的轻量启发式实现（len(str) // 4，中文同样 // 4）。这是有意的近似，不追求精确，只需要量级正确。
Pydantic 对象的估算：当前只处理 dict/list/str/int/float/bool，遇到其他类型退化为 len(str(payload)) // 4。重构后如果 context 里开始出现 Pydantic 对象（方向一落地后），需要先 model_dump() 再估算，或者在 estimate_tokens 里加 isinstance(payload, BaseModel) 分支处理。[待定：context 里 Pydantic 对象的 token 估算策略，取决于方向一落地后 context 里实际存什么类型]

## 三、pressure_level() 返回值语义

返回 1（normal）/ 2（soft reset）/ 3（hard reset），和现有一致。soft_ratio 默认 0.60，hard_ratio 默认 0.80，从 config/settings.py 读取而不是硬编码在 __init__ 默认参数里。

## 四、build_handoff_artifact() 方法

这个方法现在只是从 StateStore 读取数据拼接结构，实际上属于 ChampionTracker 的职责（它是 Meta Workflow 业务逻辑）。重构后考虑把它移到 ChampionTracker 里，ContextManager 只保留纯计算逻辑（estimate_tokens、pressure_level、should_reset）。[待定：build_handoff_artifact 是留在 ContextManager 里还是移到 ChampionTracker，倾向于后者]

## 五、soft reset 和 hard reset 的真正闭环

这是 Harness Layer 1 当前最大的未落地项。should_reset() 当前只是返回 bool，没有触发任何行为。
soft reset（level 2）：裁剪 context["chat_history"]，只保留最近 N 条（N 从 settings 读，建议 5-10 条），其余丢弃。这是一个纯内存操作，不涉及 StateStore 读写。
hard reset（level 3）：更重，需要：调用 build_handoff_artifact 从 StateStore 构建 handoff 快照，写入 context["handoff_artifact"]，然后建议 Runner 在下一个 LLM Skill 调用时把 handoff_artifact 作为 system prompt 的补充内容注入。注意：hard reset 不重启 Runner，只是清理 context 并提供结构化的恢复上下文，LLM Skill 在 execute 时检测 context.get("handoff_artifact") 并利用它。
ContextManager 新增方法 async perform_soft_reset(context: dict, max_history: int = 8) -> None 和 async perform_hard_reset(context: dict, run_id: str, state_store) -> None，由 ExecutionObserver 在检测到对应 level 时调用。[待定：具体由谁调用 perform_reset，Observer 还是 Runner 直接读取 pressure level 后决定]