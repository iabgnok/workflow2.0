# Workflows 层的改动总结

workflows/ 变化汇总：

meta/main_workflow.step.md：prev_defects? / escalation_level? 标可选，更新 version
meta/workflow_planner.step.md：更新 version，去掉前缀标签
meta/workflow_designer.step.md：prev_defects? / escalation_level? 标可选，更新 version
meta/quality_evaluator.step.md：删 blockquote 注释，escalation_level? 标可选，更新 version
dev/hello_world.step.md：迁移到 templates/ 和 tests/fixtures/workflows/，不再留在 dev/
registry/index.json：从 workflows/index.json 迁移，路径变更，格式不变
templates/example_linear.step.md：新增，三步线性流 few-shot 示例
templates/example_with_on_reject.step.md：新增，带 on_reject 循环的 few-shot 示例