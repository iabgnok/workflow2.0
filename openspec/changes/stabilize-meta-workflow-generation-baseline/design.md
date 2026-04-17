## Context

Meta workflow 当前失败模式具有跨模块特征：
1. Prompt 语义与结构化输出 schema 不一致（Generator 提示要求 Markdown，但代码强制结构化对象）。
2. Planner 蓝图字段与 Generator 输入契约不对齐（`action_type` 自由文本，缺少与可执行技能集合的一致性约束）。
3. `on_reject` 回路将 defects 逐轮累积，导致上下文快速膨胀并引入重复/过时噪声。
4. Evaluator 有明确评分维度，但 Generator 不可见，修复过程缺少目标导向。
5. E2E 测试只验证运行状态，不验证审批状态与评分阈值，导致“假阳性成功”。

约束：
- 需要兼容现有 Runner/Skill 调度主链路，避免一次性重构全部 Agent 协议。
- 需在 DeepSeek 结构化输出能力波动下提升稳定性，优先采用确定性校验与轻量修复。
- 变更应优先提升“可执行正确性”基线，再逐步提升语义质量。

## Goals / Non-Goals

**Goals:**
- 统一 Planner/Generator/Evaluator 的最小契约，使生成结果在进入评审前具备可执行性。
- 降低 reject 回路提示污染，提升多轮修复的有效收敛率。
- 将 Evaluator 关键标准暴露给 Generator，提升首轮命中率。
- 在 E2E 层面建立质量门禁（审批+评分），让测试结果可用于回归决策。

**Non-Goals:**
- 不在本次变更中替换 LLM 供应商或引入新的大模型编排框架。
- 不对所有历史 Prompt 全量重写，仅覆盖 Planner/Generator 与本变更相关内容。
- 不引入重量级自动修复推理链，仅处理可确定性修正的问题（如 action 名映射、协议结构补齐）。

## Decisions

1. Prompt 契约改为“结构化输出优先”
- 决策：重写 `generator_system_v1.md`，删除 Markdown 产物格式规则，按 `StructuredWorkflowArtifact` 字段说明输出要求，并提供 JSON few-shot 示例。
- 同时在 Prompt 中注入：
  - `registered_skills` 白名单
  - Evaluator 评分维度摘要（结构、可执行性、完整性、约束遵循等）
- 原因：消除“Markdown vs JSON”双重指令冲突，减少 schema 偏离。
- 备选方案：保留 Markdown 规则并在后处理做解析转换。未采纳，因为转换层增加错误面且无法解决语义冲突。

2. Planner→Generator action 语义对齐采用“白名单约束 + 显式映射”
- 决策：Planner prompt 显式注入 `registered_skills`，要求 `action_type` 仅从白名单选择；Generator 侧保留兼容映射层，将 `action_type` 规范化到 `action` 字段。
- 原因：在保持接口兼容的同时，阻断未注册技能进入执行链路。
- 备选方案：直接修改 Planner schema 字段名并全链路破坏式升级。未采纳，因为回归成本高。

3. Reject 缺陷传递策略采用“最近一轮 + 去重摘要”
- 决策：`runner._reject()` 不再无限 append 全历史 defects；默认仅携带最近一轮 defects，同时附带上一轮修复状态摘要。
- 原因：降低提示污染与上下文 token 压力，保留必要历史信息。
- 备选方案：保留全量历史并做复杂优先级排序。未采纳，因为复杂度高且收益不稳定。

4. 引入 Generator 后的确定性预检关卡
- 决策：在进入 Evaluator 前执行：
  - action 合法性校验（含白名单检查与近似匹配修复）
  - 协议错误检查（结构字段、引用关系、必填项）
- 对可自动修复错误做一次确定性修正并记录修正日志；不可修复错误直接形成缺陷反馈。
- 原因：用低成本确定性机制吸收可预见错误，减少无效 LLM 评审轮次。
- 备选方案：全部交由 Evaluator 打分后再 reject。未采纳，因为 token 成本高且反馈滞后。

5. E2E 质量门禁升级为“运行成功 + 质量达标”
- 决策：在关键 e2e 用例增加断言：`status == APPROVED` 与 `score >= threshold`（阈值默认 60，可配置）；保留成功率测试但纳入可见执行路径（CI 定时或可选门禁）。
- 原因：防止“流程可跑但质量失败”被误判为通过。
- 备选方案：仅记录分数不阻断测试。未采纳，因为无法形成工程约束。

6. 结构化输出稳定性采用“降复杂度 + 重试兜底”
- 决策：收敛可选字段和嵌套层级，并在验证失败时执行有限重试（含明确失败原因反馈）。
- 原因：兼容 DeepSeek 等模型在复杂 schema 下的遵循波动。
- 备选方案：立即切换模型。未采纳，因为涉及成本与依赖审批。

## Risks / Trade-offs

- [Risk] 过度约束 action 可能降低 Planner 生成灵活性 → Mitigation: 保留可配置扩展白名单并提供映射表。
- [Risk] 自动修正可能引入“看似合法但语义偏移”的结果 → Mitigation: 仅允许确定性修正，保留修正审计日志并进入 Evaluator 二次审查。
- [Risk] 质量阈值过高导致测试波动 → Mitigation: 阈值配置化并引入分层测试策略（快速回归/慢速统计）。
- [Risk] Prompt 重写后短期行为分布变化 → Mitigation: 增加对比测试与灰度开关，必要时回滚至旧 prompt。

## Migration Plan

1. 编写并落地 Prompt 变更（Planner/Generator），保留旧版本文件备份或开关。
2. 在 Generator 后接入确定性验证层，并输出结构化修正报告。
3. 修改 Runner 的 reject 缺陷携带策略，补充回路摘要逻辑。
4. 更新 E2E 断言与日志编码配置，保证报告可读和可统计。
5. 在 CI/本地分别执行核心 e2e 与成功率测试，观察 3-5 轮稳定性。
6. 如指标下降，按“提示词开关 -> 自动修正开关 -> 新断言阈值”顺序回退。

## Open Questions

- `action_type` 到 `action` 的规范映射应位于 Planner 产物层还是 Generator 预处理层？
- 自动修正规则是否需要按 skill 类型区分（IO/LLM/flow）？
- 成功率阈值（70%）在不同模型供应商下是否需要分环境配置？
- Evaluator 评分维度摘要应固定内嵌还是由 `evaluator_system_v1.md` 自动提取生成？
