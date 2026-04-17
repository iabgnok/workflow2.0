## Why

工作流资源目录当前存在几个问题：meta/ 工作流版本过时（缺少可选变量标记）、hello_world.step.md 是手写测试文件却混在 dev/ 生成目录中、index.json 和 .step.md 文件混放不利于独立管理、缺少 Generator 的少样本模板目录。需要重组目录结构，更新 Meta Workflow 到 v2.0。

## What Changes

- **meta/ 工作流更新至 v2.0**：
  - main_workflow.step.md：prev_defects?、escalation_level? 标记为可选
  - workflow_designer.step.md：prev_defects?、escalation_level? 标记为可选
  - quality_evaluator.step.md：删除注释块引用、escalation_level? 标记为可选
  - workflow_planner.step.md：版本更新，移除前缀标签
- **新增 `templates/` 目录**：两个少样本示例文件
  - `example_linear.step.md`：三步线性流（file_reader → llm_prompt_call → file_writer）
  - `example_with_on_reject.step.md`：带 on_reject 循环（Generator → Condition → Evaluator）
- **index.json 迁移**：从 `workflows/index.json` 移到 `workflows/registry/index.json`
- **hello_world.step.md**：从 dev/ 迁移到 `templates/` 和 `tests/fixtures/workflows/`

## Capabilities

### New Capabilities
- `workflow-templates`: 少样本模板目录，为 Generator Prompt 提供标准示例
- `workflow-registry-separation`: 注册元数据与工作流文件分离，各自独立生命周期

### Modified Capabilities

## Impact

- Meta Workflow 的 .step.md 文件格式更新（可选变量标记）
- WorkflowRegistry 的 index_path 默认值改为 `workflows/registry/index.json`
- Generator Prompt 的少样本示例从 templates/ 目录读取
- dev/ 目录仅包含 LLM 生成的工作流（不再混入手写文件）
