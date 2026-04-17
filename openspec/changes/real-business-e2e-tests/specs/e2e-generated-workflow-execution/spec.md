## ADDED Requirements

### Requirement: 生成工作流执行测试
测试套件 SHALL 提供一个端到端测试，将 Meta Workflow 生成的 `WorkflowModel` 序列化为临时 `.step.md` 文件，通过 `Runner` 执行，并断言运行成功。

#### Scenario: 将 WorkflowModel 写入临时文件并由 Runner 执行
- **WHEN** 已有合法 `WorkflowModel`（来自真实生成或 fixture），将其通过 `WorkflowParser` 序列化为 `.step.md` 格式写入临时文件，使用注入了 Mock Skill 的 `Runner` 执行
- **THEN** `runner.run()` 返回 `{"status": "success", ...}`，所有步骤均被调度

#### Scenario: Mock Skill 覆盖所有动态 action
- **WHEN** `WorkflowModel` 中包含 LLM action（如 `llm_planner_call`、`llm_generator_call`）
- **THEN** 所有 action 均由 Mock Skill 处理，不发起真实 LLM 调用，每个 Mock Skill 返回步骤输出变量的空 dict

#### Scenario: 空步骤工作流安全执行
- **WHEN** 生成的 `WorkflowModel` 步骤数为 0（LLM 输出异常情况）
- **THEN** Runner 直接返回 `{"status": "success"}` 且不抛出异常

### Requirement: WorkflowModel 到临时文件的序列化
测试工具 SHALL 提供将 `WorkflowModel` 转换为可被 `ProtocolService.parse_workflow_file()` 解析的临时 `.step.md` 文件的方法。

#### Scenario: 序列化后可被协议层解析
- **WHEN** `WorkflowModel` 被序列化并写入临时 `.step.md` 文件
- **THEN** 调用 `ProtocolService().parse_workflow_file(tmpfile)` 不抛出异常，返回 `(WorkflowModel, parsed_dict)` 二元组

#### Scenario: 序列化保留步骤 action 和 io 映射
- **WHEN** 含 `action`、`inputs`、`outputs` 的步骤被序列化
- **THEN** 解析回的步骤中 `action`、`inputs`、`outputs` 与原始 `WorkflowModel` 一致
