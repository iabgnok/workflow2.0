## Context

Runner 是 MyWorkflow 的执行心脏。V1-V4 迭代中不断向 Runner 堆叠功能，导致其成为 God Object。设计纲领明确要求"Runner ≤150 行"，通过五个子模块分担复杂度。

## Goals / Non-Goals

**Goals:**
- Runner 只保留步骤循环编排逻辑，≤150 行
- 每个子模块单一职责，可独立测试
- ExecutionHooks 定义清晰的五条约定（async/无返回/异常隔离/FIFO/上下文只读）
- 异常处理路径明确：SkillNotFoundError、EscalationLimitExceeded 不被吞

**Non-Goals:**
- 不改变工作流的执行语义（步骤顺序、条件跳过、on_reject 路由）
- 不改变 simpleeval 的沙箱配置
- 不引入并行步骤执行能力

## Decisions

### Decision 1: StepExecutor 不做条件求值和状态持久化
**选择**: StepExecutor 只管"给定一个步骤和上下文，执行并返回输出"
**理由**: 条件求值在主循环里做（可能跳过整个步骤），状态持久化在主循环里做（需要知道步骤 ID 序列），这些不是"单步执行"的内在职责。

### Decision 2: ExecutionHooks 异常隔离
**选择**: Hook 方法内部的异常不传播到 Runner 主循环
**理由**: Hook 是业务逻辑注入，其异常不应中断引擎的步骤执行。异常在 Hook 内部被日志记录后静默处理。

### Decision 3: on_reject 路由逻辑保留在 Runner
**选择**: on_reject/Escalation Ladder 逻辑不委派给子模块
**理由**: 这是"步骤循环编排"的核心：根据 evaluator_report 决定是否跳回、增加 escalation_level、清理 chat_history。这些决策需要全局视角（步骤序列、计数器），放在主循环里最清晰。

### Decision 4: ConditionEvaluator 返回 (skip, reason) 元组
**选择**: 返回元组而非抛异常
**理由**: 条件不满足是正常分支（跳过步骤），不是错误。InvalidExpression 时也不跳过（继续执行），只记录警告。

## Risks / Trade-offs

- **[Risk] Runner 精简后可能遗漏边界情况**: 从 650 行重写为 150 行，容易遗漏某个条件分支。→ **Mitigation**: 逐方法对照旧代码迁移，每迁移一个方法都有对应测试。
- **[Risk] Hook 异常隔离可能隐藏严重错误**: ChampionTracker 的错误被静默处理。→ **Mitigation**: Hook 异常必须写 logger.error，监控日志可以捕获。
