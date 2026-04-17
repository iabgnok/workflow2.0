## Context

协议层是 MyWorkflow 的纪律核心，当前 12 个文件共约 1200 行代码，ZERO 外部依赖（仅 stdlib + Pydantic）。V1-V4 迭代中积累了函数重复和职责散布问题，但整体架构合理。此次重构不改变协议层的定位和对外接口，重点是内部整理和新增结构化路径支持。

## Goals / Non-Goals

**Goals:**
- 消灭三个跨文件重复函数（normalize_var_name、extract_metadata_inputs、is_optional_var）
- 确立 gatekeeper 为 action 合法性检查的唯一权威
- 新增 WorkflowModel 直接校验能力（不依赖文件路径）
- 新增协议错误到 Generator defect 格式的转换接口
- 标记遗留文本清洗函数为 Deprecated

**Non-Goals:**
- 不改变 dry_run 的条件分支分析能力（已知局限性，保留现状）
- 不改变 ProtocolIssue/ProtocolReport 的基本结构
- 不移动文件位置（protocol/ 目录结构保持不变）
- 不改变 error_codes 的现有码值

## Decisions

### Decision 1: utils.py 放在 protocol/ 内部而非顶层 utils
**选择**: `protocol/utils.py`
**理由**: 这些函数的上下文是"协议层如何处理变量名"，是协议层的内部工具，不应暴露给其他层。保持协议层的自治性。

### Decision 2: action 检查归 gatekeeper 独占
**选择**: 删除 security_scan._scan_action_whitelist() 和 generator._validate_actions()，保留 gatekeeper 的实现
**理由**: 三处重复导致逻辑不一致风险。Gatekeeper 检查的错误码和位置信息更完整，且能按步骤精确报告。

### Decision 3: scan_workflow_model 作为新增函数而非替换 scan_artifact_security
**选择**: 新增 `scan_workflow_model()` 函数，保留 `scan_artifact_security()`
**理由**: 已持久化的 `.step.md` 文件仍需文本扫描（WorkflowRegistry 验证路径），两个函数服务不同场景。Generator 结构化路径完全落地后，文本扫描路径才可废弃。

### Decision 4: normalizer 旧函数标记 Deprecated 而非删除
**选择**: 保留 `sanitize_artifact_for_engine()` 和 `normalize_generated_artifact()` 但标注 Deprecated
**理由**: WorkflowRegistry 和回放路径仍间接依赖这些函数。完全删除需要等 Generator 结构化路径打通且所有 dev/ 文件重新生成。

### Decision 5: from_structured_artifact() 放在 generator.py（已决策）
**选择**: 放在 `skills/llm/generator.py` 内作为 `to_workflow_model()` 方法
**理由**: models.py 是协议层核心，不应 import generator（会造成依赖倒置：协议层 → 技能层）。转换逻辑放在知道 StructuredWorkflowArtifact 结构的 generator.py 更合理。依赖方向保持：技能层 → 协议层（单向）。

### Decision 6: RunResult 放在 engine/models.py（已决策）
**选择**: 放在 `engine/models.py`
**理由**: RunResult 是引擎层的概念（Runner 的返回类型），不属于协议层职责。保持协议层纯粹性。engine/ 层可以有自己的 models.py 存放引擎层专属类型。

## Risks / Trade-offs

- **[Risk] gatekeeper 检查顺序变更可能影响错误信息**: 从汇总报错改为逐步报错。→ **Mitigation**: 错误码不变，只是 location 从 None 改为 step:N，对消费方更友好。
- **[Risk] normalizer Deprecated 函数长期留存**: 如果结构化路径迟迟不落地，废弃标记可能永远不被清理。→ **Mitigation**: 在 tasks.md 的最后阶段加入清理检查项。
- **[Risk] scan_workflow_model 和 scan_artifact_security 行为微妙差异**: 文本扫描和对象扫描的覆盖范围可能不完全一致。→ **Mitigation**: 两个函数使用同一份 DANGER/CONFIRM 关键词列表，差异只在扫描目标（文本 vs step.content 字段）。
