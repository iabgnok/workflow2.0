## 1. 测试环境配置

- [x] 1.1 在 `new_src/tests/e2e/` 目录创建 `__init__.py`
- [x] 1.2 创建 `new_src/tests/e2e/conftest.py`：session-scope fixture 用 `python-dotenv` 从项目根目录加载 `.env`（`load_dotenv(root/.env, override=True)`），每次测试后调用 `LLMClientRegistry.reset()` 清除 LLM 客户端缓存
- [x] 1.3 在 `pyproject.toml` 中注册 `e2e` pytest marker（`markers = ["e2e: real LLM end-to-end tests"]`），并配置 `asyncio_mode = "auto"`（如未配置）

## 2. 需求生成工作流测试（Test 1）

- [x] 2.1 创建 `new_src/tests/e2e/test_meta_workflow_generation.py`，文件顶部设置 `pytestmark = [pytest.mark.e2e, pytest.mark.asyncio, pytest.mark.skipif(not os.environ.get("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY not set")]`
- [x] 2.2 实现 `test_meta_workflow_generates_valid_workflow_model()`：调用 `run_meta_workflow(filepath=<meta_main_workflow.step.md 绝对路径>, initial_context={"requirement": "构建一个读取 CSV 文件并输出统计摘要的工作流"}, workflows_root=<new_src/agent/workflows 绝对路径>, db_path=":memory:")`
- [x] 2.3 断言：`result["status"] == "success"`，`result["context"]["final_artifact"]` 为 `WorkflowModel` 实例，`len(model.steps) > 0`，`model.metadata.name` 为非空字符串
- [x] 2.4 断言每个 step 的 `action` 字段为非空字符串（不断言具体 action 名，允许 LLM 自由发挥）

## 3. 调用生成工作流测试（Test 2）

- [x] 3.1 创建 `new_src/tests/e2e/test_generated_workflow_execution.py`，同样设置 `pytestmark` 含 `e2e` 和 `skipif`
- [x] 3.2 实现 `workflow_model_fixture`（module-scope）：直接构造一个最简 `WorkflowModel`（2 步，action 分别为 `mock_skill_a`、`mock_skill_b`），用于 Test 2，不依赖 Test 1 的 LLM 输出，保证测试确定性
- [x] 3.3 实现 `_serialize_workflow_to_tempfile(model: WorkflowModel) -> str`：将 `WorkflowModel` 序列化为 `.step.md` YAML front-matter + Markdown 步骤格式，写入 `tempfile.NamedTemporaryFile(suffix=".step.md")` 并返回路径
- [x] 3.4 实现 `test_runner_executes_generated_workflow()`：加载 fixture `WorkflowModel`，序列化为临时文件，构造带 Mock Skill 的 `Runner`（参照 `test_runner_integration.py` 中 `_make_runner()` 模式），执行 `runner.run()`，断言 `result["status"] == "success"`
- [x] 3.5 验证序列化往返正确性：`ProtocolService().parse_workflow_file(tmpfile_path)` 不抛异常，返回步骤数与原始 `WorkflowModel` 一致

## 4. 集成验证

- [x] 4.1 在 `new_src/` 目录下执行 `pytest tests/e2e/ -m e2e -v`，确认 Test 1 和 Test 2 均通过（或在无 Key 环境下均 skip）
- [x] 4.2 执行 `pytest tests/ -m "not e2e"` 确认现有单元测试不受影响，全部通过
- [x] 4.3 检查 Test 1 输出日志，确认 Planner → Designer → Evaluator 三个子工作流均被调度（通过 `logging.INFO` 输出验证）
