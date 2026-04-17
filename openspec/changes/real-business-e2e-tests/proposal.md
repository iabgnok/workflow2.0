## Why

现有单元测试和集成测试全部使用 Mock 隔离 LLM 调用，无法验证真实 LLM（DeepSeek）驱动下系统的端到端正确性。需要一套"真实业务测试"，在真实 API Key 配置下：①通过 Meta Main Workflow 接受自然语言需求并生成可执行工作流（需求生成工作流）；②将生成的工作流对象交给 Runner 实际执行（调用生成的工作流）。两个测试均需要与真实 LLM 交互，因此只在 `.env` 配置完整时运行。

## What Changes

- 新增 `new_src/tests/e2e/` 目录，存放端到端真实业务测试
- 新增 `test_meta_workflow_generation.py`：使用真实 DeepSeek LLM，传入 `requirement` 字符串，驱动 Meta Main Workflow（Planner → Designer → Evaluator 闭环），断言输出为合法 `WorkflowModel`
- 新增 `test_generated_workflow_execution.py`：将生成的 `WorkflowModel` 通过 Runner 执行（子步骤继续 Mock，重点验证 Runner 对动态生成工作流的驱动能力）
- 新增 `conftest.py`：管理 `.env` 加载、LLM 客户端重置、Skip 标记（无 API Key 则跳过）
- `pyproject.toml` 补充 `e2e` pytest marker 及相关配置

## Capabilities

### New Capabilities
- `e2e-meta-workflow-generation`: 真实 LLM 驱动的 Meta Main Workflow 端到端测试，验证需求 → WorkflowModel 全链路
- `e2e-generated-workflow-execution`: 将 LLM 生成的 WorkflowModel 注入 Runner 执行，验证动态工作流的运行链路

### Modified Capabilities
<!-- 无现有 spec 层级的需求变更 -->

## Impact

- 仅影响 `new_src/tests/` 下新增文件，不修改生产代码
- 依赖 `.env` 中 `DEEPSEEK_API_KEY`（或其他 provider 配置）有效才运行
- 需要 `pytest-asyncio`、`pytest` 已在 dev 依赖中（已满足）
- 测试默认通过 `@pytest.mark.e2e` 标记隔离，不影响现有 CI 单元测试
