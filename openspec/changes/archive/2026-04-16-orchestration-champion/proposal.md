## Why

Runner 当前内含约 12 个 Champion 相关方法（指纹计算、复合复用检查、回放验证、工作流注册、Champion 更新等），这些是 Meta Workflow 特有的业务逻辑，不应在通用引擎中。需要将这些逻辑抽取到独立的编排层，通过 ExecutionHooks 接口注入 Runner，让引擎完全不知道任何具体工作流。

## What Changes

- **新增 `agent/orchestration/` 目录**和 `champion_tracker.py`
- `ChampionTracker` 继承 `ExecutionHooks`，实现四个钩子方法
- 从 Runner 迁移 12 个方法：指纹计算、复合复用、回放、注册、Champion 更新
- Runner 只需接受一个可选的 `hooks: ExecutionHooks` 参数，Meta Workflow 运行时传入 ChampionTracker 实例

## Capabilities

### New Capabilities
- `champion-tracker`: Champion 业务逻辑编排模块，通过 ExecutionHooks 注入 Runner，管理工作流复用、评审、注册和回放

### Modified Capabilities

## Impact

- Runner 不再包含任何 Champion/注册/回放逻辑
- 新增 `agent/orchestration/` 目录，单文件 `champion_tracker.py`
- ChampionTracker 依赖 StateStore、WorkflowRegistry、ProtocolService
- Meta Workflow 的 main.py 入口需要构造 ChampionTracker 并传入 Runner
