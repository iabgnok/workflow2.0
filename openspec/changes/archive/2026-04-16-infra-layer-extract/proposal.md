## Why

当前引擎层（`agent/engine/`）混合了两类职责截然不同的代码：核心执行逻辑（Runner、Parser）和外部资源适配器（SQLite 存储、LLM 工厂、技能注册表等）。这导致引擎层文件过多（10+ 文件）、依赖关系复杂、单元测试需要 mock 大量外部资源。需要将纯粹的外部适配器抽取到独立的 `infra/` 层，让引擎层只关注执行编排。

## What Changes

- **新增 `agent/infra/` 目录**，从 `agent/engine/` 迁移 7 个文件：
  - `state_store.py` → 新增 `AbstractStateStore` 接口 + 重命名为 `SQLiteStateStore`，JSON 序列化（禁止 pickle），9 个标准方法
  - `llm_factory.py` → 新增 `LLMClientRegistry` 单例，按 (provider, model, temperature, json_mode) 缓存客户端实例
  - `skill_registry.py` → 递归扫描 `skills/llm/`、`skills/io/`、`skills/flow/` 子目录，新增 `build_skill_manifest()` 和 `SkillNotFoundError`
  - `workflow_registry.py` → 新增 `register_workflow_model(model)` 方法，DryRun 为注册前置条件
  - `context_manager.py` → 新增 `perform_soft_reset()` / `perform_hard_reset()` 方法
  - `variable_mapper.py` → 新增 `VariableMappingError` 异常类型
  - `error_policy.py` → 三级幂等性策略（L0/L1/L2），L2 不自动重试
- 所有文件从 `from agent.engine.xxx import` 改为 `from agent.infra.xxx import`

## Capabilities

### New Capabilities
- `infra-state-store`: 抽象化持久存储接口 + SQLite 实现，支持 JSON 序列化和 Champion 追踪
- `infra-llm-registry`: LLM 客户端注册中心，实例缓存和统一构建接口
- `infra-skill-registry`: 技能发现注册中心，递归扫描 + manifest 生成
- `infra-adapters`: 其他基础设施适配器（workflow_registry、context_manager、variable_mapper、error_policy）

### Modified Capabilities

## Impact

- engine/ 目录文件数从 10+ 减少到 5-7 个（核心执行逻辑）
- 所有 import engine.state_store / engine.llm_factory 等的代码需更新路径
- infra/ 层可独立测试（mock 外部资源）
- Runner、StepExecutor 等仅依赖 infra 的接口而非具体实现
