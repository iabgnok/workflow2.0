# runner.py 重构实现细节

## 一、职责边界（最重要）

重构后 Runner 只负责三件事：驱动步骤循环、处理路由决策、协调各子模块的调用顺序。不再自己实现任何具体的执行逻辑、业务判断、压力观测或持久化细节。目标行数 ≤ 150 行。
凡是现在在 runner.py 里做的事，按以下原则分配：

条件求值 → ConditionEvaluator
单步执行 → StepExecutor
断点续传 → ResumeStrategy
Champion/注册/回放 → ChampionTracker（通过 ExecutionHooks 注入）
压力观测 → ExecutionObserver（通过 Hook 触发）

## 二、__init__ 构造函数

- 参数列表保持可注入：接受 state_store、skill_registry、context_manager、hooks（ExecutionHooks 实例，默认为 None）均为可选，支持测试时 mock 注入。新增 hooks: ExecutionHooks | None = None 参数，取代当前的 workflow_name 字符串判断机制。

- SkillRegistry 初始化路径：从 settings.py 读取 skills_dir，不再用 os.path.join(os.path.dirname(__file__), '..', 'skills', 'atomic') 硬编码相对路径。SkillRegistry 改为递归扫描 skills/llm/、skills/io/、skills/flow/ 三个子目录。

- skill_manifest 注入时机：SkillRegistry 扫描完成后，调用 registry.build_skill_manifest() 生成结构化技能描述字符串，存入 self.context["skill_manifest"]（替代当前的 registered_skills 纯名称列表）。两个 key 都写入，registered_skills 保留用于 Gatekeeper 校验，skill_manifest 用于注入 LLM Prompt。

- context_window_tokens：从 settings.py 读取默认值，不再读 os.environ.get("MYWORKFLOW_CONTEXT_WINDOW_TOKENS", "120000")。构造函数里不做 int() 转换的 try/except，由 settings 的 Pydantic 类型保障。

- parser 初始化位置保持不变：WorkflowParser(filepath) 在 __init__ 里创建，但 parse() 调用推迟到 run() 里，和现在一样。

- __init__ 末尾不再直接注入 registered_skills 到 context：改为注入 skill_manifest（结构化描述）和 registered_skills（名称列表）两个 key，并在 ExecutionContext.runtime 里记录（方向一的 context 三层分离落地后再推进，当前阶段暂时保持 flat dict 兼容写法，标注 [待定]）。

## 三、run() 主方法结构

整个 run() 方法重构为五段清晰的职责：
*段一：解析与初始化*

await self.state_store.connect() 保持不变，放在 try 块开头。
调用 ProtocolService.parse_workflow_file(self.filepath) 得到 workflow_model（WorkflowModel Pydantic 对象）和 steps。steps 此后统一是 list[StepModel]（Pydantic 对象），不再是 plain dict 列表——这是方向一的核心落地点之一。当前阶段如果 StepModel 还未完全就绪，steps 暂时仍是 list[dict]，但 Runner 主循环里不再直接用 step['id'] 这样的字典访问，改用辅助函数统一封装。【此处是方向一和协议层 models.py 重构的结合点，取决于 StepModel 是否已在 protocol/models.py 里落地，[待定]】
current_run_id = run_id or str(uuid.uuid4())，start_step_id = 1，jump_back_counters: dict[int, int] = {}，这三个局部变量保持不变。
self.context.setdefault('prev_defects', []) 和 self.context.setdefault('escalation_level', 1) 保持不变，放在解析段末尾。
*段二：断点续传*

整块断点续传逻辑提取到 ResumeStrategy.resume(run_id, state_store, context) 里，返回 (hydrated_context, start_step_id)。Runner 这里只调用一次，不展开细节。_hydrate_champion_context() 移入 ChampionTracker，在 ResumeStrategy 内部通过 hooks 调用。
断点续传的逻辑：传入 run_id 且找到历史状态 → ResumeStrategy 恢复；传入 run_id 但没有历史状态 → 打 warning 并作全新任务开始；不传 run_id → 全新任务。三个分支在 ResumeStrategy 里处理，Runner 不展开。
*段三：执行前准备*

await self.state_store.save_run_state(current_run_id, workflow_name, "running", start_step_id, self.context) 保持，作为崩溃恢复锚点。
observer.on_run_start(run_id, workflow_name) 触发 ExecutionObserver，替代现在的 _observe_context_pressure("run_start")。
await self.hooks.on_run_start(run_id, context) —— hooks 调用，允许 ChampionTracker 在这里做 composite champion reuse 检查（替代现在的_try_enable_composite_champion_reuse）。
*段四：主循环（这是 Runner 真正的核心）*

while current_step_index < len(steps): 循环体结构变为：
a. 取出当前 step = steps[current_step_index]，打日志。

b. await self.hooks.on_step_before(run_id, step) —— hooks 调用（ChampionTracker 在这里决定是否 replay champion，替代_try_replay_champion_for_meta）。如果 hook 返回 skip=True，则 save_step_state(status="replayed") 后 current_step_index += 1; continue。

c. skip, reason = await self.condition_evaluator.eval(step.condition, self.context) —— 条件求值委托给   ConditionEvaluator。结果 skip=True 则打日志跳过，current_step_index += 1; continue。

d. await self.state_store.save_run_state(...) —— 崩溃恢复锚点，在执行前保存（保持现有逻辑）。

e. observer.on_step_start(step_id) —— 触发 Observer 压力采样。

f. output = await self.step_executor.execute(step, self.context) —— 单步执行全部委托给 StepExecutor，包含前置断言、变量注入、skill 调度、错误策略、后置断言。StepExecutor 正常返回则 output 是 dict[str, Any]。

g. self.context.update(output) —— 写回 context，保持现有行为。

h. observer.on_step_end(step_id, output) —— 触发 Observer 结束采样。

i. await self.state_store.save_step_state(run_id, step_id, "success", output, self.context)。

j. on_reject 路由判断（这段留在 Runner 里，不外移，因为它是控制流的核心）：
    只从当前 step 的 output 里读 evaluator_report，不读 self.context 历史（保持现有防误跳逻辑）。
    await self.hooks.on_step_after(run_id, step, output) —— 先让 hook 处理（ChampionTracker 在这里更新 champion）。
    读 step.on_reject（从 StepModel 字段读，不再是 step.get('on_reject')）。
    is_rejected = output.get("evaluator_report", {}).get("status") == "REJECTED"。不再需要_parse_evaluator_report()，因为方向一落地后 evaluator_report 在 output 里就是 EvaluatorReport Pydantic 对象，直接访问 .status。【当前过渡期保持兼容写法，[待定]】
    is_rejected and step.on_reject is not None → 进入 Escalation Ladder 逻辑（见下）。
    否则 current_step_index += 1，循环继续。

k. Escalation Ladder 逻辑（保持在 Runner 里）：
    jump_back_counters[target_id] += 1，得到 current_escalation。
    current_escalation >= 4：打 error 日志，向 state_store 写 failed 状态，raise EscalationLimitExceeded(last_feedback=...)（自定义异常，不再是 Exception）。
    否则：写入 self.context["escalation_level"] = current_escalation，self.context["prev_defects"] = output["evaluator_report"].defects（Pydantic 对象，方向一落地前暂时用 .get("defects", [])），self.context.pop("evaluator_report", None)，self.context["chat_history"] = []。
    查找 target_index，找不到则 raise ValueError（不再是通用 Exception）。
    current_step_index = target_index; continue.
*段五：工作流完成*

await self.hooks.on_workflow_complete(run_id, context) —— ChampionTracker 在这里触发注册和回放（替代_register_if_meta_workflow）。
await self.state_store.save_run_state(run_id, workflow_name, "completed", len(steps), self.context)。
await observer.flush(run_id) —— Observer 落盘压力统计。
返回 RunResult(run_id=current_run_id, status="success", context=self.context) —— 返回值改为 RunResult Pydantic 类型，不再是 plain dict。【RunResult 类型需在 protocol/models.py 或新建的 engine/models.py 里定义，[待定]】

## 四、异常处理结构

当前的两个 except 块（SkillNotFoundError 和通用 Exception）逻辑重复，重构后合并为：

except SkillNotFoundError：直接 raise，不重新包装，让上层感知具体类型。
except EscalationLimitExceeded：打 error 日志，写 state，re-raise。
except Exception as e：打 error 日志，写 failed state，re-raise。

三个 except 块都调用 await observer.flush(run_id) 确保压力统计落盘，然后 re-raise。不再在 except 里重复 save_run_state 和 save_step_state——StepExecutor 负责执行时的 step 级别持久化，Runner 的 except 只负责 run 级别的状态更新。
finally 块保持 await self.state_store.close()，不变。

## 五、从 Runner 中完全移除的方法

以下方法不再出现在 runner.py 里，它们的去向：

|方法|去向|
|---|---|
|_observe_context_pressure()|ExecutionObserver|
|_flush_context_pressure_stats()|ExecutionObserver|
|_truncated_context_log()|内联到日志工具或 ExecutionObserver|
|_parse_evaluator_report()|方向一落地后消失（类型化后不需要）|
|_get_skill()|StepExecutor 内部|
|_report_score()|ChampionTracker|
|_requirement_fingerprint()|ChampionTracker|
|_extract_blueprint_features()|ChampionTracker|
|_blueprint_fingerprint()|ChampionTracker|
|_update_champion()|ChampionTracker|
|_on_step_after()|ChampionTracker|
|_hydrate_champion_context()|ChampionTracker，由 ResumeStrategy 调用|
|_try_replay_champion_for_meta()|ChampionTracker|
|_on_step_before()|ChampionTracker|
|_try_enable_composite_champion_reuse()|ChampionTracker|
|_on_run_start()|ChampionTracker|
|_attempt_generated_workflow_replay()|ChampionTracker|
|_on_workflow_complete()|ChampionTracker|
|_register_if_meta_workflow()|ChampionTracker|

## 六、ExecutionHooks 接口定义（附带在 runner 分析里）

execution_hooks.py 定义一个 ExecutionHooks 基类（或 Protocol），有以下几个方法，全部 async，全部有默认空实现（什么都不做），可被子类覆盖：

on_run_start(run_id, context) —— Runner 开始执行时
on_step_before(run_id, step) → StepHookResult(skip: bool) —— 每步执行前，允许返回 skip
on_step_after(run_id, step, output) —— 每步执行后，在 on_reject 路由判断之前
on_workflow_complete(run_id, context) —— 工作流所有步骤跑完后

ChampionTracker 继承 ExecutionHooks，覆盖上述四个方法。普通工作流运行时不传 hooks，Runner 使用默认的空实现，所有 champion 相关逻辑完全不存在于执行路径中。

## 七、一个关键的向后兼容决策

当前 sub_workflow_call 内部会递归创建一个新的 Runner 实例。重构后这个 Runner.__init__ 签名变了（新增 hooks 参数），sub_workflow_call 创建子 Runner 时不传 hooks，子工作流的执行是纯引擎行为，不注入任何业务 hook。Champion 相关逻辑只在顶层 Meta Workflow 的 Runner 里存在，子工作流 Runner 是干净的。这个逻辑需要在 sub_workflow_call.py 里明确体现.
