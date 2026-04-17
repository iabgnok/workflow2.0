## Context

工作流资源是 MyWorkflow 的数据层。当前 meta/、dev/、index.json 混放在同一目录，缺少模板目录。重构后目录结构更清晰，各部分有独立的管理策略。

## Goals / Non-Goals

**Goals:**
- Meta Workflow 升级到 v2.0（可选变量标记、移除遗留注释）
- 新增 templates/ 目录提供少样本示例
- index.json 迁移到 registry/ 子目录
- hello_world.step.md 归位到正确位置

**Non-Goals:**
- 不改变 .step.md 的 DSL 语法
- 不改变 Meta Workflow 的步骤数量或执行逻辑
- 不新增 Meta Workflow 步骤

## Decisions

### Decision 1: 可选变量使用 `?` 后缀标记
**选择**: `prev_defects?` 格式
**理由**: 与 DSL 设计纲领一致，Parser 已支持 `?` 后缀识别，runtime_assertions 的 is_optional_var() 可正确处理。

### Decision 2: templates/ 不被 WorkflowRegistry 扫描
**选择**: templates/ 是纯资源目录，不自动注册
**理由**: 模板是 Generator Prompt 的参考素材，不是可执行的注册工作流。自动注册会污染 index.json。

## Risks / Trade-offs

- **[Risk] Meta Workflow 版本升级可能影响现有运行**: 正在运行的工作流可能依赖旧版本字段。→ **Mitigation**: 版本升级只增加可选标记和移除注释，不改变执行语义。StateStore 中的历史运行不受影响。
