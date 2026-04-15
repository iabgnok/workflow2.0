# resume_strategy.py（新增，从 Runner 拆出）

## 一、为什么新增这个文件

断点续传逻辑当前嵌在 run() 的开头部分，大约 20 行，涉及 StateStore 的多次查询和 context 的多次 update()。这段逻辑本身很稳定，但和主循环混在一起使主方法难以阅读。拆出后可以独立测试"有历史状态恢复"、"无历史状态新建"、"历史状态损坏时降级"这三个场景。

## 二、职责范围

ResumeStrategy 只负责：给定 run_id 和 state_store，查询历史状态，更新 context，返回 start_step_id。不负责：Champion 相关数据的恢复（这属于 ChampionTracker，通过 ExecutionHooks.on_run_start 触发）。

## 三、resume(run_id, state_store, context) -> int 方法（async）

传入 run_id 为 None 或空字符串：直接返回 1（全新任务）。
传入 run_id 有值：

state = await state_store.load_run_state(run_id)
找到历史状态：

context.update(state["context"]) 恢复 state 层
context.update(state["meta_context"]) 恢复 meta 层（如果有）
start_step_id = state["current_step_id"]
latest_step = await state_store.load_latest_step_state(run_id, status="success")
如果 latest_step 存在：context.update(latest_step["full_context"])；context.update(latest_step["meta_full_context"])；start_step_id = max(start_step_id, latest_step["step_id"] + 1)
找到历史状态：打 info 日志："找到历史状态，从 step {start_step_id} 继续"

没找到历史状态：打 warning 日志 "未找到 run_id 历史状态，作为全新任务开始"，返回 1。

返回值是 start_step_id: int，Runner 用它确定 current_step_index = start_step_id - 1。
Champion 数据的恢复不在这里：_hydrate_champion_context 对应的逻辑移入 ChampionTracker，由 ExecutionHooks.on_run_start 触发，ResumeStrategy 完成后 Runner 再触发 hook，保持顺序：先恢复状态，再恢复 champion。