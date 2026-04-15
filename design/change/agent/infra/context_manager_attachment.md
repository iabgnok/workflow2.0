# infra/context_manager.py（从 engine/context_manager.py 搬移）

## 一、soft_reset 实现细节

perform_soft_reset(context: dict, max_history: int) -> None 同步方法（不需要 IO，纯内存操作）：

取 history = context.get("chat_history", [])
如果 len(history) <= max_history，不做任何事（还没到需要裁剪的程度）
否则：context["chat_history"] = history[-max_history:]，只保留最后 N 条
打日志："[Context Soft Reset] 对话历史从 {len(history)} 条裁剪至 {max_history} 条"
max_history 从 settings.CONTEXT_SOFT_RESET_MAX_HISTORY（默认值 8）读取，允许在 settings 里调整

## 二、hard_reset 实现细节

async perform_hard_reset(context: dict, run_id: str, state_store: AbstractStateStore, next_objective: str | None = None) -> None：

调 build_handoff_artifact(run_id, state_store, next_objective) 构建结构化交接快照
把 handoff_artifact 写入 context["handoff_artifact"]（已存在则更新）
清空 context["chat_history"] = []（彻底清除，不像 soft reset 只裁剪）
打日志："[Context Hard Reset] 对话历史已清空，handoff_artifact 已构建"
注意：hard reset 不停止 Runner，只是准备好 handoff 数据，下次 LLM Skill 在 execute_step 里检测 context.get("handoff_artifact") 并把它注入 system prompt

谁调用 perform_hard_reset：ExecutionObserver 在 on_step_end 里检测到 pressure_level == 3 时，调 context_manager.perform_hard_reset(context, run_id, state_store)。这需要 ExecutionObserver 持有 context_manager 引用——在 DefaultExecutionObserver.__init__ 里注入。[待定：ExecutionObserver 的构造函数参数，是否直接持有 context_manager 还是通过回调]

## 三、build_handoff_artifact 的去向

如 engine 分析中所述，这个方法移到 ChampionTracker 里更合适（它是 Meta Workflow 的业务概念）。但 ContextManager.perform_hard_reset 需要构建一个基础的 handoff artifact（包含 var_snapshot、run_status 等）来支持上下文恢复。
解法：ContextManager 里保留一个简化版的 _build_basic_handoff(run_id, state_store) 只构建基础结构（var_snapshot、run_status、current_step_id），不包含 champion_json / last_feedback 这些 Meta Workflow 专属字段。ChampionTracker 的完整版 build_handoff_artifact 在此基础上追加 champion 数据。[待定：是否合并为一个方法还是保持分层]

## 四、estimate_tokens 的 Pydantic 对象支持

新增 isinstance(payload, BaseModel) 分支：return self.estimate_tokens(payload.model_dump())，避免 Pydantic 对象退化为 repr(payload) // 4 的低精度估算。