## Context

新 `new_src/` 架构已完成所有单元测试和 Mock 集成测试，覆盖 Runner、ChampionTracker、Protocol、Skills 等模块。但所有测试均通过 `MagicMock` / `AsyncMock` 隔离了真实 LLM 调用，无法验证：

1. **Meta Main Workflow 生成链路**：Planner（`llm_planner_call`）→ Designer（`llm_generator_call`）→ Evaluator（`llm_evaluator_call`）在真实 DeepSeek API 下能否正常协作，输出合法 `WorkflowModel`。
2. **动态工作流执行链路**：LLM 生成的 `WorkflowModel`（包含动态步骤、actions、inputs/outputs）能否被 `Runner` 正确驱动执行。

`.env` 中 `DEEPSEEK_API_KEY` 已配置，满足真实调用条件。

## Goals / Non-Goals

**Goals:**
- 编写两个真实业务端到端测试，与真实 LLM 交互
- Test 1：给定自然语言需求 → Meta Main Workflow 完整运行 → 断言输出为合法 `WorkflowModel`
- Test 2：将 Test 1 生成的 `WorkflowModel` 写入临时 `.step.md` 文件 → Runner 执行 → 断言 `status == "success"`（子步骤用 Mock Skill）
- 通过 `@pytest.mark.e2e` 标记隔离，不污染现有 CI 单元测试套件
- `conftest.py` 负责 `.env` 加载（从项目根目录）、LLM 客户端重置、无 Key 自动 skip

**Non-Goals:**
- 不修改任何生产代码（`agent/`、`config/`、`main.py`）
- 不断言 LLM 输出的语义质量（如工作流步骤是否"合理"），只验证结构合法性
- 不测试 ChampionTracker 复用逻辑（保留给现有 Mock 集成测试）
- 不支持 Gemini/OpenAI provider（可扩展，但本次仅 DeepSeek）

## Decisions

### Decision 1：测试入口使用 `run_meta_workflow()` 而非直接构造 Runner

`new_src/main.py` 中的 `run_meta_workflow()` 函数已封装完整基础设施组装（`SQLiteStateStore`、`WorkflowRegistry`、`ProtocolService`、`ChampionTracker`、`Runner`），且接受 `workflows_root` 等参数，可精准指向 `new_src/agent/workflows/meta/main_workflow.step.md`。

直接复用此函数可避免在测试中重复组装，且与生产路径完全一致。

**Alternatives considered:** 直接 `new Runner(filepath=...)` → 需要手动组装所有基础设施，重复代码多，且可能遗漏 ChampionTracker 注入。

### Decision 2：Test 2 生成工作流执行使用 Mock Skill

Test 1 输出的 `WorkflowModel` 步骤中的 `action`（如 `llm_generator_call`、`file_reader` 等）在 Test 2 执行时不应再调用真实 LLM（避免双重费用、不确定性）。改用 `SkillRegistry` 注入 Mock Skill，覆盖所有 action，让 Runner 只验证编排逻辑。

这与 `test_runner_integration.py` 中的做法一致，保持测试模式统一。

### Decision 3：`.env` 从项目根目录加载

`config/settings.py` 的 `SettingsConfigDict(env_file=".env")` 依赖工作目录为 `new_src/`。测试通过 `conftest.py` 中 `os.chdir()` 或 `python-dotenv` 显式加载根目录 `.env`，确保 `DEEPSEEK_API_KEY` 被读取。

实际做法：`conftest.py` 在 session scope 中用 `dotenv.load_dotenv(root/.env, override=True)` 注入环境变量，再触发 `settings` 重新读取（或通过 `Settings(_env_file=...)` 覆盖）。

### Decision 4：使用 `pytest.mark.skipif` 在无 API Key 时跳过

```python
pytestmark = pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set"
)
```

保证在未配置 `.env` 的 CI 环境中测试自动跳过，不报错。

## Risks / Trade-offs

- [LLM 输出不确定性] → Test 1 只断言结构合法（`isinstance(model, WorkflowModel)` 且 `len(steps) > 0`），不断言步骤内容，降低 flakiness
- [测试速度慢] → E2E 测试标记为 `@pytest.mark.e2e`，默认不加入 CI，手动运行
- [API 费用] → 每次运行 Test 1 消耗 ~1-3 次 DeepSeek 调用；Test 2 全 Mock，无额外费用
- [工作目录问题] → pytest 默认从项目根或 `new_src/` 启动，通过 conftest 显式加载 `.env` 规避路径依赖
