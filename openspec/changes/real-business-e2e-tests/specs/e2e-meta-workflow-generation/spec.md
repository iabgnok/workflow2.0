## ADDED Requirements

### Requirement: E2E Meta Workflow Generation Test
测试套件 SHALL 提供一个端到端测试，使用真实 LLM（DeepSeek）驱动 Meta Main Workflow，接受自然语言需求字符串，输出合法的 `WorkflowModel` 对象。

#### Scenario: 给定需求字符串，Meta Workflow 完整运行并输出 WorkflowModel
- **WHEN** `DEEPSEEK_API_KEY` 环境变量已设置，且调用 `run_meta_workflow(filepath=meta_main_workflow.step.md, initial_context={"requirement": "..."})`
- **THEN** 返回字典中 `status == "success"`，且 `context["final_artifact"]` 为 `WorkflowModel` 实例，且 `len(workflow_model.steps) > 0`

#### Scenario: 无 API Key 时测试自动跳过
- **WHEN** `DEEPSEEK_API_KEY` 环境变量未设置或为空字符串
- **THEN** 测试被 `pytest.mark.skipif` 自动跳过，不报错、不失败

#### Scenario: LLM 输出结构合法性断言
- **WHEN** Meta Workflow 运行成功
- **THEN** `WorkflowModel.metadata.name` 为非空字符串，每个 step 均有 `id`、`name`、`action` 字段，`action` 为已注册技能之一

### Requirement: E2E 测试环境配置
测试套件 SHALL 在 `conftest.py` 中自动从项目根目录 `.env` 加载环境变量，无需用户手动设置 shell 变量。

#### Scenario: conftest 加载 .env 并注入环境变量
- **WHEN** pytest session 启动，`conftest.py` 中调用 `load_dotenv(root_env_path, override=True)`
- **THEN** `os.environ["DEEPSEEK_API_KEY"]` 等配置项可被 `config.settings.Settings` 读取

#### Scenario: LLM 客户端缓存在测试间隔离
- **WHEN** 每个测试结束后
- **THEN** `LLMClientRegistry.reset()` 被调用，防止跨测试缓存污染
