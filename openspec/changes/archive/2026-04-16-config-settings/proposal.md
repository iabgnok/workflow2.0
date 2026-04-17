## Why

当前项目配置散落在 6 个以上文件中（llm_factory.py、runner.py、context_manager.py、error_policy.py、workflow_registry.py 等），每个文件各自读取 `os.environ`，导致：配置难以追踪、默认值不一致、环境变量命名无统一规范、测试时需要 mock 多处环境变量。需要引入统一配置层，作为整个重构的基础设施。

## What Changes

- 新增 `config/settings.py`，使用 `pydantic-settings` 的 `BaseSettings` 类，集中管理所有配置项
- LLM 相关配置（provider、model、api_key、base_url）从 `llm_factory.py` 的散落读取迁移到 Settings
- 引擎参数（context_window_tokens、soft/hard ratio）从 `runner.py`/`context_manager.py` 硬编码迁移到 Settings
- 路径配置（db_path、workflows_root、skills_root、prompts_root）统一入口
- 默认工作流输入（`with_runtime_input_defaults` 的 5 个硬编码值）迁移到 `default_workflow_inputs` 字段
- 模块级单例 `settings = Settings()`，全项目统一通过 `from config.settings import settings` 访问

## Capabilities

### New Capabilities
- `unified-settings`: 基于 pydantic-settings 的集中配置管理，支持环境变量和 .env 文件自动加载，类型验证，模块级单例访问

### Modified Capabilities

## Impact

- 所有直接读取 `os.environ` / `os.getenv` 的代码需改为读取 `settings` 对象
- `pyproject.toml` 需添加 `pydantic-settings` 依赖
- `.env.example` 需更新以反映所有支持的配置项
- 后续模块（infra/llm_factory, infra/state_store, protocol/infer_inputs 等）均依赖此变更
