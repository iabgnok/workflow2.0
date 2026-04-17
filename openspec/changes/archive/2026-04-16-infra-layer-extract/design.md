## Context

engine/ 目录当前承担了执行编排 + 外部适配两类职责。适配器代码（SQLite、LLM API、文件系统）的变更频率和测试方式与核心执行逻辑完全不同。分层后各自可以独立演进和测试。

## Goals / Non-Goals

**Goals:**
- 将 7 个外部适配器文件从 engine/ 迁移到 infra/
- 为 StateStore 引入抽象接口，支持未来替换存储后端
- 为 LLM 客户端引入注册中心模式，避免重复创建
- 为 SkillRegistry 支持递归子目录扫描和 manifest 生成
- 保持所有现有功能不变，仅改变代码组织结构

**Non-Goals:**
- 不引入依赖注入框架
- 不更改 SQLite 表结构或数据格式
- 不更改 LLM 提供商的支持列表
- 不更改 error_policy 的三级策略逻辑

## Decisions

### Decision 1: AbstractStateStore 接口 + SQLiteStateStore 实现
**选择**: 新增抽象基类，重命名现有实现
**理由**: 未来可能需要替换存储后端（如 PostgreSQL），接口抽象使得切换零成本。当前只有一个实现，不过度设计。

### Decision 2: LLMClientRegistry 缓存键为 (provider, model, temperature, json_mode)
**选择**: 四元组作为缓存键
**理由**: 相同配置的 LLM 客户端可安全复用，避免每次 skill 调用都创建新实例。temperature 和 json_mode 影响行为，必须作为键的一部分。

### Decision 3: SkillRegistry 递归扫描替代平铺扫描
**选择**: 从 `skills/atomic/*.py` 改为递归扫描 `skills/llm/`、`skills/io/`、`skills/flow/`
**理由**: 技能重组后分散在三个子目录，平铺扫描无法覆盖。递归扫描自动适配目录结构变化。

## Risks / Trade-offs

- **[Risk] import 路径大面积变更**: 所有引用 engine.xxx 的代码需要更新。→ **Mitigation**: 使用 IDE 全局替换，变更前后运行全部测试。
- **[Risk] AbstractStateStore 接口可能过早抽象**: 当前只有 SQLite 一个实现。→ **Mitigation**: 接口只包含现有 9 个方法，不预设未来需求，保持极简。
