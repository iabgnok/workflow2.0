## 1. Meta Workflow 更新

- [x] 1.1 更新 `main_workflow.step.md`：version→2.0，prev_defects?/escalation_level? 标记可选
- [x] 1.2 更新 `workflow_designer.step.md`：version→2.0，prev_defects?/escalation_level? 标记可选
- [x] 1.3 更新 `quality_evaluator.step.md`：version→2.0，删除注释块引用，escalation_level? 标记可选
- [x] 1.4 更新 `workflow_planner.step.md`：version→2.0，移除前缀标签

## 2. Templates 目录

- [x] 2.1 创建 `new_src/agent/workflows/templates/` 目录
- [x] 2.2 创建 `example_linear.step.md`（三步线性流少样本）
- [x] 2.3 创建 `example_with_on_reject.step.md`（on_reject 循环少样本）
- [x] 2.4 将 `hello_world.step.md` 复制到 templates/ 和 tests/fixtures/workflows/

## 3. Registry 分离

- [x] 3.1 创建 `new_src/agent/workflows/registry/` 目录
- [x] 3.2 迁移 `index.json` 到 `registry/index.json`
- [x] 3.3 更新 WorkflowRegistry 的默认 index_path 配置

## 4. 验证

- [x] 4.1 使用 Parser 解析所有更新后的 meta/ 工作流，确认无错误
- [x] 4.2 使用 Gatekeeper 验证 templates/ 模板文件
- [x] 4.3 确认 dev/ 目录不包含手写文件
