## Context

MyWorkflow 项目经历 V1-V4 演进，配置管理始终是临时方案：每个模块自行读取 `os.environ`，默认值分散在各文件里。这导致配置不可测试、不可追踪、不可统一覆盖。pydantic-settings 是 Python 生态中成熟的解决方案，与项目已有的 Pydantic 依赖完全兼容。

## Goals / Non-Goals

**Goals:**
- 所有配置项集中在一个文件中，有类型标注和默认值
- 支持环境变量 + .env 文件自动加载（pydantic-settings 原生能力）
- 提供模块级单例，消除各模块的 `os.getenv` 调用
- 路径字段支持空字符串（由消费方推导默认路径），也支持显式覆盖

**Non-Goals:**
- 不改变任何消费方的业务逻辑，只替换配置读取方式
- 不引入配置文件热重载机制
- 不处理 repo_path 的 os.getcwd() 动态默认值问题（留给消费方处理）

## Decisions

### Decision 1: 使用 pydantic-settings 而非自定义配置类
**选择**: pydantic-settings BaseSettings
**理由**: 项目已依赖 Pydantic，pydantic-settings 提供环境变量绑定、.env 支持、类型验证，零额外学习成本。
**替代方案**: python-dotenv + dataclass（缺少类型验证）、dynaconf（过重）、plain dict（无类型安全）。

### Decision 2: 路径字段空字符串策略
**选择**: 路径字段默认为空字符串，消费方检查是否为空并自行推导
**理由**: Settings 不应该知道项目的绝对路径结构，也不应在字段默认值中调用 `os.path` 函数。各模块（StateStore、SkillRegistry 等）已有 `os.path.join(os.path.dirname(__file__), ...)` 的推导逻辑，只需加一层 `if settings.xxx: use it, else: derive` 的判断。
**替代方案**: validator 里调 os.path（在 import 时产生副作用，不利于测试）。

### Decision 3: 模块级单例而非依赖注入
**选择**: `settings = Settings()` 在模块级创建
**理由**: 简单直接，全项目通过 import 访问。测试时可通过环境变量或 `Settings(llm_provider="test")` 构造独立实例。
**替代方案**: DI 容器（增加复杂度，与项目规模不匹配）。

## Risks / Trade-offs

- **[Risk] 导入顺序副作用**: Settings 在 import 时读取环境变量。→ **Mitigation**: 这是 pydantic-settings 的标准行为，测试中可通过 monkeypatch 或构造新实例隔离。
- **[Risk] default_workflow_inputs 中 repo_path 的动态默认值**: os.getcwd() 不能作为 Pydantic 字段默认值。→ **Mitigation**: repo_path 默认为空字符串，`with_runtime_input_defaults()` 在运行时检查并填充 os.getcwd()。
