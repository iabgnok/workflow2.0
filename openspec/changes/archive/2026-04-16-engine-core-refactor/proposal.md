## Why

Runner 当前约 650 行，承担了步骤执行、条件求值、状态恢复、上下文压力观测、Champion 管理、工作流注册等多项职责。这导致 Runner 难以理解、难以测试、难以修改。需要将 Runner 拆分为多个单职责子模块，目标 ≤150 行，只保留"步骤循环编排"的核心职责。

## What Changes

- **Runner（重构）**：精简至 ≤150 行，五阶段结构：解析 → 恢复 → 准备 → 主循环 → 完成。所有复杂逻辑委派给子模块
- **新增 `step_executor.py`**：单步执行器（变量注入 → 前置断言 → 技能查找执行 → 后置断言）
- **新增 `condition_evaluator.py`**：条件求值器（simpleeval 沙箱，返回 skip/reason）
- **新增 `resume_strategy.py`**：断点恢复策略（加载状态 → 注水上下文 → 确定起始步骤）
- **新增 `execution_hooks.py`**：执行钩子协议（async/无返回/异常隔离/FIFO/上下文只读）+ StepHookResult
- **新增 `execution_observer.py`**：上下文压力采样与遥测（替代 Runner._observe_context_pressure）
- **Parser（收窄）**：只处理手写 `.step.md` 文件，LLM 输出走结构化路径
- **step_validator.py（删除）**：职责被 StepExecutor 吸收

## Capabilities

### New Capabilities
- `engine-step-executor`: 单步执行子模块，职责清晰（变量注入→断言→执行→断言）
- `engine-condition-eval`: 条件求值子模块（simpleeval 沙箱隔离）
- `engine-resume`: 断点恢复子模块（状态加载→上下文注水→起始步骤确定）
- `engine-hooks`: 执行钩子协议（业务逻辑注入接口）
- `engine-observer`: 执行观测子模块（压力采样与遥测）

### Modified Capabilities

## Impact

- Runner 从 650 行精简至 ≤150 行，只驱动步骤循环
- step_validator.py 被删除，其逻辑分散到 StepExecutor 的前后置断言
- Parser 不再处理 LLM 生成物（那些走 Generator → WorkflowModel 的结构化路径）
- ExecutionHooks 成为 Runner 与业务逻辑（ChampionTracker）的唯一桥梁
- Runner 的异常处理更明确：SkillNotFoundError 直接重抛、EscalationLimitExceeded 直接重抛
