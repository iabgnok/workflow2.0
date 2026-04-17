## 1. Runner 成功信号语义

- [ ] 1.1 在 `agent/engine/runner.py` 将固定 `status="success"` 改为调用 `_derive_final_status(self.context)`。
- [ ] 1.2 在 Runner 类新增 `_derive_final_status(context)`，实现 `success/rejected/approved_unverified/replay_failed` 派生规则，并加入 `__skip_auto_replay__` 特判（内层回放 Runner 直接返回 `success`）。
- [ ] 1.3 执行目标 e2e（`tests/e2e/test_meta_workflow_generation.py::test_meta_workflow_generates_valid_workflow_model`），确认状态语义已生效并可暴露真实失败。

## 1.5 基线测量（改动 1 后立即执行，不改任何代码）

- [ ] 1.5.1 在完成任务 1.x 后，运行 20 次 meta workflow 基线测试，记录四个状态分布：`success / rejected / approved_unverified / replay_failed`。
- [ ] 1.5.2 根据基线决策后续改动优先级：`success >= 70%` 优先进入任务 5；`rejected` 占比最高优先执行任务 4；`approved_unverified` 占比高优先排查 replay 触发条件；`replay_failed` 占比高优先执行任务 2+3。
- [ ] 1.5.3 记录基线数字作为后续改动收益对比锚点（anchor）。

## 2. Generator 内容可扫描化

- [ ] 2.1 在 `agent/skills/llm/generator.py` 组装 `WorkflowStep` 前合成 `synthetic_content`（name/action/inputs/outputs 拼接）。
- [ ] 2.2 为 `WorkflowStep` 填充 `content=synthetic_content`，不改变既有输入输出映射逻辑。
- [ ] 2.3 运行协议安全扫描相关测试（含 `security_scan`），确认新增 `content` 不破坏现有行为且可见风险关键词。

## 3. ChampionTracker 前置硬规则体检

- [ ] 3.1 在 `agent/orchestration/champion_tracker.py:on_step_before` 中保持现有复用跳过逻辑不变。
- [ ] 3.2 在 `step.id == _EVALUATOR_STEP_ID` 且存在 `final_artifact` 时执行 `_check_protocol_errors`，并将缺陷合并到 `prev_defects`。
- [ ] 3.3 运行 ChampionTracker 相关单测，确认前置注入与 `on_run_end` 复检可同时工作（defense in depth）。

## 4. Evaluator 阈值容噪调整

- [ ] 4.1 编辑 `prompts/evaluator_system_v1.md`，将“通过阈值必须 100 分”调整为“>= 90 分”。
- [ ] 4.2 同步更新评分表：stage 1-2 使用 `>= 90`，stage 3+ 使用 `logic_closure >= 85`、`safety_gate >= 90`、其余维度忽略。
- [ ] 4.3 复跑目标 e2e，记录与改动 1 后相比的通过率变化。

## 5. e2e 底线断言与成功率量化

- [ ] 5.1 在 `tests/e2e/test_meta_workflow_generation.py` 为主用例增加 `result["status"] == "success"` 断言，并输出 replay 诊断信息。
- [ ] 5.2 新增可选 slow 测试：运行 20 次 meta workflow，断言成功率 `>= 70%`（至少 14/20）。
- [ ] 5.3 在失败样本中记录失败阶段分布（`rejected / approved_unverified / replay_failed`），用于定位瓶颈层。
- [ ] 5.4 在本地执行 e2e 测试集并汇总成功率结果，作为本变更验收依据。

## 6. 端到端验收与回归检查

- [ ] 6.1 按顺序执行关键验证：改动 1 e2e、任务 1.5 基线测量、改动 2 protocol scan、改动 3 champion 单测、改动 4 e2e、改动 5 新增测试。
- [ ] 6.2 检查是否存在非预期回归（普通 workflow 状态语义、技能注册、注册流程）。
- [ ] 6.3 更新变更记录，标注成功信号语义变更与新增状态枚举的使用约定。
