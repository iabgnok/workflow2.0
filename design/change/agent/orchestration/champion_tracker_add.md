# orchestration/champion_tracker.py（新增，从 Runner 拆出）

## 一、为什么拆出，拆什么

Runner 里以下方法全部属于"Meta Workflow 的 Champion 竞选业务逻辑"，不属于通用执行引擎：_update_champion、_hydrate_champion_context、_try_replay_champion_for_meta、_try_enable_composite_champion_reuse、_attempt_generated_workflow_replay、_register_if_meta_workflow、_requirement_fingerprint、_blueprint_fingerprint、_extract_blueprint_features、_report_score。这 10 个方法（加上 _parse_evaluator_report、_truncated_context_log 共 12 个）
这使 runner.py 膨胀到 691 行，其中真正属于引擎调度的核心循环只有约 100 行。

## 二、ChampionTracker 继承 ExecutionHooks

class ChampionTracker(ExecutionHooks)，覆盖四个 hook 方法，每个方法内部是纯业务逻辑，不调用任何引擎内部接口，只通过构造函数注入的依赖操作。

## 三、__init__

构造函数接受：

state_store: AbstractStateStore（读写 run_meta、champion_json）
workflow_registry: WorkflowRegistry（注册生成的工作流）
protocol_service: ProtocolService（注册前校验）
workflows_root: str 和 index_path: str（WorkflowRegistry 构建子 Runner 回放时需要）

由 main.py 或 CLI 层在启动 Meta Workflow 的 Runner 时构建 ChampionTracker 实例并传入 Runner(hooks=champion_tracker)。

## 四、on_run_start(run_id, context) hook

对应原有逻辑：_try_enable_composite_champion_reuse + _hydrate_champion_context。
执行顺序：

- 计算 requirement_fingerprint（SHA256 of context.get("requirement", "")）
- 计算 blueprint_fingerprint（SHA256 of 从 context.get("workflow_blueprint") 提取的结构特征）
- 两个 fingerprint 都非空时：查 state_store.load_latest_champion_by_composite(req_fp, bp_fp)
- 找到匹配的 champion：调用内部 _hydrate_context(run_meta, context) 把 champion 数据写入 context
- 没找到：不做任何事，正常开始

*_hydrate_context* 内部方法（原 _hydrate_champion_context）：从 run_meta 里取 champion_json、last_feedback、registration_audit、context_pressure，写入 context 对应 key。如果 champion 的 evaluator_report.status == "APPROVED" 且有 final_artifact，同时写入 context["__reuse_champion__"] = True，供 on_step_before 判断是否跳过重跑。

## 五、on_step_before(run_id, step, context) -> StepHookResult

对应原有逻辑：_try_replay_champion_for_meta。
判断逻辑：context.get("__reuse_champion__") == True 且满足以下任一条件则返回 StepHookResult(skip=True)：

step.id == 2（Designer 步骤）且 context.get("final_artifact") 存在
step.id == 3（Evaluator 步骤）且 context.get("__reuse_champion__") 存在

关键设计决策：现有实现通过硬编码 step id（2 和 3）来判断是否跳过，并且通过 workflow_name == "Meta Main Workflow" 来过滤。重构后：

workflow_name 判断去掉——ChampionTracker 实例只会被 Meta Workflow 的 Runner 持有，不会被其他工作流的 Runner 拿到，所以不需要再检查 workflow_name
step id 的硬编码保留（2 和 3 是 Meta Main Workflow 的 Designer 和 Evaluator 步骤），但加明确注释说明这是 Meta Workflow 专属逻辑，不是通用引擎能力。[待定：是否把这个 step id 做成可配置参数，而不是硬编码，由 main.py 在构建 ChampionTracker 时传入]

返回 StepHookResult(skip=True) 时，Runner 负责持久化 save_step_state(status="replayed", ...) 并打日志，ChampionTracker 不直接操作 StateStore。

## 六、on_step_after(run_id, step, output, context) hook

对应原有逻辑：_update_champion。
只在 output.get("evaluator_report") 存在时触发（Evaluator 步骤的输出）。
_parse_evaluator_report 消失：方向一落地后 evaluator_report 在 output 里是 EvaluatorReport Pydantic 对象，直接访问 .status、.defects、.score，不需要防御性解析。过渡期兼容写法：检查是 dict 还是 Pydantic 对象，用 .get("status") 或 .status 分别访问。
APPROVED 时的 champion 更新：

计算 candidate：{"score": report.score, "final_artifact": context.get("final_artifact"), "evaluator_report": report_dict, "blueprint_fingerprint": ..., "blueprint_features": ...}
load_run_meta(run_id) 取现有 champion
candidate.score >= existing_champion_score → 更新 champion，写 state_store.save_run_meta(run_id, champion_json=candidate, ...)
更新 context：context["champion_json"]、context["last_feedback"]、context["handoff_artifact"]

REJECTED 时：不更新 champion_json，但更新 last_feedback 和 requirement_fingerprint / blueprint_fingerprint 的持久化（供后续轮次的 composite 匹配用）。
fingerprint 计算方法（_requirement_fingerprint 和 _blueprint_fingerprint）：从 Runner 移过来，作为 ChampionTracker 的私有方法。_blueprint_fingerprint 内部调 _extract_blueprint_features（也移过来）。逻辑不变：从 context["workflow_blueprint"] 提取 workflow_name、step_count、每步的 action/inputs/outputs，JSON 序列化后 SHA256。
_report_score 静态方法：移过来。接受 report: dict | EvaluatorReport，返回 int，兼容两种类型。

## 七、on_workflow_complete(run_id, context) hook

对应原有逻辑：_register_if_meta_workflow + _attempt_generated_workflow_replay。
注册触发条件：context.get("__skip_auto_replay__") 为 True 时跳过（防止回放 Runner 触发二次注册）；final_artifact 不存在时跳过；evaluator_report.status != "APPROVED" 时跳过。
注册流程：

调用 workflow_registry.register_workflow_model(model, description, ...) 或过渡期的 register_generated_workflow(artifact, ...)
注册成功：把 workflow_id、generated_workflow_path、registration_summary、protocol_report、dry_run 写入 context
调用 state_store.save_run_meta(run_id, registration_audit={...})
触发 _attempt_generated_workflow_replay

_attempt_generated_workflow_replay 内部方法：

解析已注册的 workflow_path，推断 required_inputs
用 with_runtime_input_defaults(context) 注入默认值
检查 missing_inputs：有缺失则写 context["generated_workflow_replay"] = {"status": "skipped", ...} 后返回
创建子 Runner（:memory: DB，不传 hooks）执行回放
把回放结果写入 context["generated_workflow_replay"]

注册失败时的协议层错误回流：注册抛异常（ProtocolGatekeeperError 或 ProtocolDryRunError）时，ChampionTracker 捕获异常，把 ProtocolReport.errors_as_defects() 的结果合并进 context["prev_defects"]，更新 context["escalation_level"]，从而触发 Runner 主循环在下一个适当时机让 Generator 修复——但这里有一个控制流问题：on_workflow_complete 是在所有步骤完成之后触发的，Runner 主循环已经结束，无法再回头。正确的机制是：注册失败时，ChampionTracker 把失败信息记录在 context 里，由调用方（main.py 或 CLI）决定是否重新启动一轮 Meta Workflow 执行，传入这次的失败信息作为 prev_defects 的初始值。[待定：注册失败后的重试机制，这超出了当前重构范围，标注为 [待定]]