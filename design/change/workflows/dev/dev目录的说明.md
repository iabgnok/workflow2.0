# dev/ 目录的说明

workflows/dev/ 目录

## 一、整体管理策略

dev/ 目录存放 LLM 生成的工作流产物。这个目录的文件完全由 WorkflowRegistry 管理，不应该有人工编辑的文件（除了用于测试或示范的特例）。

## 二、现有文件的处理

hello_world.step.md：这是手工编写的测试/示例工作流，放在 dev/ 目录不合理——dev/ 应该是机器生成产物的存放处，手工文件会混淆两者。重构后迁移到：

如果作为测试用途：移到 tests/fixtures/workflows/hello_world.step.md
如果作为示例用途：移到 workflows/templates/hello_world.step.md

两个用途都有，倾向于保留两份（或软链接）：templates/ 里一份供人参考和 Generator 的 few-shot 引用，tests/fixtures/workflows/ 里一份供测试用。
其他 LLM 生成的文件（champion_*.step.md、filereadworkflow_*.step.md 等）：这些是历史生成产物，保留但不做任何修改。重构后 WorkflowRegistry 的注册路径会写到 workflows/registry/index.json（新路径），这些历史文件对应的索引条目在 index.json 里仍然有效，路径不变。
.gitignore 建议：dev/ 目录下的文件建议加入 .gitignore（除了 hello_world.step.md 这样的示例文件）。LLM 生成产物是运行时数据，不应该纳入版本控制。[待定：.gitignore 策略是否纳入重构范围]