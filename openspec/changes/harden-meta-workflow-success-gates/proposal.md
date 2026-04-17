## Why

Meta workflow 当前的 `status=success` 仅表示运行流程完成，无法反映产物是否真正可用（评审通过且回放跑通）。同时，Evaluator 100 分硬阈值对 LLM 波动过于敏感，且 Generator 未填充 step `content` 导致安全扫描存在盲区，最终让 e2e 的“成功”信号与真实质量脱钩。

## What Changes

- 将 Runner 最终状态从“流程执行成功”升级为“产出质量成功”，对 meta workflow 基于 `evaluator_report` 与 `generated_workflow_replay` 派生最终状态。
- 调整 Evaluator 系统提示词阈值：核心维度由 100 改为可容忍噪声的 90/85 区间，保留工程与人设维度阈值。
- 在 Generator 组装 `WorkflowStep` 时合成并填充 `content` 字段，使协议安全扫描可见 `action` 与 IO 关键字。
- 将 ChampionTracker 的协议硬规则检查前移到 Evaluator 之前，并将缺陷注入 `prev_defects`，保留 `on_run_end` 复检作为第二道防线。
- 收紧 e2e 断言语义（`status == success` 即代表“评审通过 + 回放跑通”），并补充成功率门槛测试（可选 slow）。

## Capabilities

### New Capabilities
- `meta-workflow-success-status`: 定义 meta workflow 最终状态派生语义，使运行结果与真实可用性一致。
- `generator-step-content-synthesis`: 定义 Generator 对 `WorkflowStep.content` 的合成策略，确保扫描器可见语义信号。

### Modified Capabilities
- `external-prompts`: 调整 evaluator prompt 评分阈值与判定表，降低 LLM 评分噪声导致的误拒。
- `champion-tracker`: 在 Evaluator 前置阶段执行协议硬规则体检并注入 `prev_defects`，从“注册前单点复检”升级为“双阶段防线”。

## Impact

- Affected code:
  - `agent/engine/runner.py`
  - `agent/skills/llm/generator.py`
  - `agent/orchestration/champion_tracker.py`
  - `prompts/evaluator_system_v1.md`
  - `tests/e2e/test_meta_workflow_generation.py`
- Behavior/API impact:
  - `run_meta_workflow` 返回的 `status` 对 meta workflow 将更细粒度（`success`/`rejected`/`approved_unverified`/`replay_failed`）。
- Quality impact:
  - e2e 成功信号与真实产出一致，可用于量化 70% 成功率目标。
