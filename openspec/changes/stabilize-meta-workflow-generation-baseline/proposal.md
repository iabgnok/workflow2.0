## Why

当前 Meta workflow 在真实 E2E 下频繁出现 `Evaluator score=0` 与多轮 REJECT，根因不是单点 bug，而是 Planner/Generator/Evaluator 之间的契约不一致、reject 回路上下文污染、以及测试只验证“可运行”不验证“可接受质量”。在继续扩展功能之前，需要先建立“结构正确且可执行”的稳定底线。

## What Changes

- 将 Generator 系统提示从 Markdown 文本产物导向，重写为结构化输出导向：以 `StructuredWorkflowArtifact` 字段契约为主，删除 Markdown 格式规则，提供 JSON few-shot 示例。
- 在 Planner 与 Generator 之间建立 action 对齐约束：Planner 注入 `registered_skills` 白名单，并限制 `action_type` 仅可引用可执行技能标识；同时定义映射/校验策略，避免未注册技能下游扩散。
- 收敛 reject 回路缺陷上下文：`on_reject` 仅传递最近一轮缺陷，或执行去重+分级后再传递，避免历史噪声持续污染生成。
- 在 Generator 与 Evaluator 之间增加确定性校验层：生成后先执行 action 合法性与协议错误检查，对可自动修复问题进行确定性修正，再进入 LLM 评审。
- 让 Generator 可见 Evaluator 核心评分维度摘要，减少“被未知标准评审”的盲修。
- 强化 E2E 质量可见性：新增对 `APPROVED` 与最低分阈值的断言，确保“成功”不仅是流程跑通，也包含输出质量。
- 改进与模型能力相关的稳态策略：降低结构化 schema 复杂度、补充重试与验证中间层，以降低弱结构化模型下的失败率波动。

## Capabilities

### New Capabilities
- `meta-workflow-quality-gates`: 为 meta workflow 增加可执行质量门禁与可统计的验收信号（审批状态、分数阈值、成功率）。

### Modified Capabilities
- `external-prompts`: 调整 Planner/Generator 提示词契约，统一结构化输出语义并注入技能白名单与评分维度摘要。
- `skill-flow-agents`: 修复 reject 回路缺陷传递策略，并约束 Planner 蓝图到 Generator 输入的 action 语义一致性。
- `workflow-model-validation`: 增加生成后确定性验证与自动修复流程，保证下游评审前的模型可执行性。
- `protocol-error-flowback`: 明确协议校验错误在生成-评估链路中的归类、回传与重试触发条件。
- `champion-tracker`: 补充 E2E 质量断言与统计口径，确保结果可量化追踪。

## Impact

- Affected code:
  - `new_src/prompts/generator_system_v1.md`
  - `new_src/prompts/planner_system_v1.md`
  - `new_src/agent/skills/llm_agents/generator.py`（或等效生成器入口）
  - `new_src/agent/engine/runner.py`
  - `new_src/tests/e2e/test_meta_workflow_generation.py`
  - 相关验证/协议检查模块（`engine`/`protocol` 子模块）
- Affected behavior:
  - Meta workflow 的生成-评估闭环将从“提示词驱动猜测”收敛为“结构契约+确定性校验+评分对齐”。
- Dependencies and systems:
  - LLM provider structured output 能力（含 DeepSeek）
  - E2E 执行环境与日志编码链路
  - 既有 OpenSpec 能力定义与测试基线
