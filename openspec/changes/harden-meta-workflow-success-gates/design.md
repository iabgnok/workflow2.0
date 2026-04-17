## Context

当前 Meta Main Workflow 的执行链路已经具备三类关键机制：
1. 协议硬规则检查（`_check_protocol_errors`）
2. LLM 评审（Evaluator）
3. 回放验证（`generated_workflow_replay`）

但三者的接线顺序与角色分工不一致：
- Runner `status` 仍以“流程执行完成”为成功信号，未绑定评审与回放结果。
- 协议硬规则主要在注册前复检，未在 Evaluator 前作为输入约束注入。
- Evaluator 提示词对关键维度要求 100 分，导致对模型波动过敏。
- Generator 生成步骤时未填充 `content`，使基于关键词的安全扫描存在漏检风险。

因此需要将流程从“LLM 单点判决”调整为“硬规则前置 + LLM 复核 + 回放事实兜底”的三段式闸门。

## Goals / Non-Goals

**Goals:**
- 让 meta workflow 的 `status=success` 精确表示“评审 APPROVED 且回放成功”。
- 在 Evaluator 执行前注入协议硬规则缺陷，减少 LLM 独立发现结构性问题的负担。
- 让安全扫描能读取到生成步骤的关键信号（action/inputs/outputs）。
- 在不新增组件的前提下提升 e2e 成功率稳定性，并可量化验证 70% 目标。

**Non-Goals:**
- 不重写 Evaluator/Generator 的核心提示词架构，仅调整阈值和已有字段使用。
- 不替换现有 Champion 注册逻辑，仅新增前置体检并保留末端复检。
- 不改变普通（非 meta）工作流的 `status` 语义。

## Decisions

### Decision 1: 在 Runner 派生最终状态而非返回固定 success
- 方案：在 Runner 增加 `_derive_final_status(context)`，并在运行结束时返回该派生状态。
- 规则（仅对 meta 语义判定对象生效）：
  - `context.get("__skip_auto_replay__") is True`：直接返回 `success`（回放内层 Runner，保持老语义，避免把回放内层误判为 `approved_unverified`）。
  - 无 `evaluator_report`：保持 `success`（兼容普通工作流）。
  - 有 report 且非 `APPROVED`：返回 `rejected`。
  - report 为 `APPROVED` 但无 replay：返回 `approved_unverified`。
  - report 为 `APPROVED` 且 replay 失败：返回 `replay_failed`。
  - report 为 `APPROVED` 且 replay 成功：返回 `success`。
- 备选方案：在测试层自行解析 context 判定成功。
  - 放弃原因：会造成业务语义分散在测试代码，运行时信号不可复用。

### Decision 2: Evaluator 阈值从“100 硬门槛”调整为“分层容噪门槛”
- 方案：在 `prompts/evaluator_system_v1.md` 中下调核心维度阈值。
- 原则：将“是否存在硬缺陷”的责任转移给协议硬规则与回放验证，LLM 评分用于语义质量复核。
- 具体阈值：

| 阶段 | logic_closure | safety_gate | engineering_quality | persona_adherence |
| --- | --- | --- | --- | --- |
| Stage 1-2 | >= 90 | >= 90 | 阈值 70 | 阈值 60 |
| Stage 3+ | >= 85 | >= 90 | 忽略 | 忽略 |

- 说明：`safety_gate` 始终保持 `>= 90`，`logic_closure` 在 Stage 3+ 放宽为 `>= 85`，由 replay 事实兜底逻辑闭合。
- 备选方案：保持 100 分并增加重试次数。
  - 放弃原因：会放大成本与不确定性，且无法从机制上减少误拒。

### Decision 3: Generator 合成并填充 `WorkflowStep.content`
- 方案：从 `name/action/inputs/outputs` 合成 `synthetic_content`，写入 step `content`。
- 预期：`scan_workflow_model` 能扫描到 `file_writer`、`shell_executor` 等关键词。
- 备选方案：改造扫描器直接读取结构化字段。
  - 放弃原因：改动面更大，超出本次“最小接线改造”目标。

### Decision 4: ChampionTracker 在 Evaluator 前执行协议体检并注入 `prev_defects`
- 方案：在 `on_step_before` 且 `step.id == _EVALUATOR_STEP_ID` 时，对 `final_artifact` 执行 `_check_protocol_errors`，结果合并至 `prev_defects`。
- 约束：保持 `on_run_end` 现有复检逻辑不变，形成纵深防御。
- 备选方案：仅在 on_run_end 检查。
  - 放弃原因：Evaluator 无法消费硬规则缺陷，LLM 仍承担主判官职责。

### Decision 5: e2e 成功断言绑定新的 status 语义
- 方案：`test_meta_workflow_generates_valid_workflow_model` 增加 `result["status"] == "success"` 断言；可选增加 slow 成功率测试（20 次，>=70%，即至少 14/20）。
- 备选方案：继续仅断言模型结构合法。
  - 放弃原因：无法覆盖“真实可用性”目标，也无法量化改动收益。

### Decision 6: 回放失败错误回流为可修复缺陷
- 方案：在 `champion_tracker._attempt_replay` 的异常分支中，将 `generated_workflow_replay.error` 封装为一条 defect 注入 `prev_defects`，供后续 Designer/Generator 轮次使用。
- 目标：避免相同回放失败模式在 `on_reject` 多轮预算中重复出现，提高修复收敛效率。
- 备选方案：仅记录日志，不回流缺陷。
  - 放弃原因：错误信息无法进入修复闭环，难以提升多轮重试的有效性。

## Affected Callers Audit

改动 1 后，以下调用点会观察到新的 `status` 枚举：
- `champion_tracker._attempt_replay`: 内层回放 Runner 必须携带 `__skip_auto_replay__` 维持老语义 `success`，避免污染外层 replay 判定。
- `tests/e2e/test_meta_workflow_generation.py`: 改动 5 会将断言升级为 `status == "success"`（语义变为“评审通过 + 回放跑通”）。
- `main.run_meta_workflow` 的外部调用方（含 CLI/脚本集成）：需确认是否存在 `if status != "success"` 的单分支处理，必要时补充 `rejected/approved_unverified/replay_failed` 分支。

未完成审计的调用方默认仅期望 `success`，改动后收到新枚举值可能触发 fallback 或错误路径，需在实施阶段逐一确认。

## Risks / Trade-offs

- [风险] 阈值降低可能放过部分边界质量问题。
  - Mitigation: 协议硬规则前置 + on_run_end 复检 + replay 兜底。

- [风险] `approved_unverified` 可能在现有调用方产生未覆盖分支。
  - Mitigation: 在 e2e 中显式断言 `success`，并在后续调用方文档中声明新状态枚举。

- [风险] 合成 content 可能引入冗余文本。
  - Mitigation: 仅使用简洁拼接，不引入额外自然语言描述，降低噪声。

- [权衡] 保留两次协议检查会有少量重复开销。
  - Mitigation: 相对运行成本可接受，换取更高的缺陷检出稳定性。

- [风险] replay 错误回流可能增加 Designer/Generator 的修复负担，导致单轮提示长度上升。
  - Mitigation: 仅注入结构化、最小必要 defect（location/type/reason/suggestion），并在后续轮次去重。

## Migration Plan

1. 更新 Runner 的最终状态派生逻辑并验证现有单测/e2e 无非预期回归。
2. 更新 Generator 的 `content` 合成写入并执行协议安全扫描相关测试。
3. 更新 ChampionTracker 的 Evaluator 前置体检并执行 orchestration 相关测试。
4. 更新 evaluator prompt 阈值并运行 meta e2e 观察成功率变化。
5. 收紧 e2e 断言并（可选）引入 slow 成功率门槛测试。

回滚策略：
- 如出现大面积误判，可回退 prompt 阈值与 Runner 派生状态逻辑；
- 保留 Generator `content` 合成与 Champion 前置体检（低风险增强）作为可独立保留项。

## Open Questions

- `approved_unverified` 是否需要在上层 CLI/日志中增加显式提示以便运维识别？
- 成功率统计测试是否固定为 `@pytest.mark.slow` 并在 CI 夜间任务执行？
