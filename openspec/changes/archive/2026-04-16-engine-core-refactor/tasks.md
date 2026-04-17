## 1. 执行钩子与数据结构

- [x] 1.1 创建 `new_src/agent/engine/execution_hooks.py`，定义 `ExecutionHooks` 基类和 `StepHookResult`
- [x] 1.2 编写 ExecutionHooks 的单元测试（默认空实现、异常隔离）

## 2. 条件求值器

- [x] 2.1 创建 `new_src/agent/engine/condition_evaluator.py`，实现 `ConditionEvaluator.eval()`
- [x] 2.2 编写条件求值的单元测试（None/truthy/falsy/NameNotDefined/InvalidExpression）

## 3. 单步执行器

- [x] 3.1 创建 `new_src/agent/engine/step_executor.py`，实现 `StepExecutor.execute()`
- [x] 3.2 实现变量注入 → 前置断言 → 技能查找 → execute_with_policy → 后置断言流水线
- [x] 3.3 编写 StepExecutor 的单元测试

## 4. 恢复策略

- [x] 4.1 创建 `new_src/agent/engine/resume_strategy.py`，实现 `ResumeStrategy.resume()`
- [x] 4.2 编写恢复策略的单元测试（新运行/有历史/无历史）

## 5. 执行观测器

- [x] 5.1 创建 `new_src/agent/engine/execution_observer.py`，实现 `DefaultExecutionObserver`
- [x] 5.2 编写观测器的单元测试

## 6. Parser 收窄

- [x] 6.1 重构 `new_src/agent/engine/parser.py`，确认只处理手写 .step.md 文件
- [x] 6.2 保留 `replace_variables()` 静态方法
- [x] 6.3 编写 Parser 的单元测试

## 7. Runner 重写

- [x] 7.1 重写 `new_src/agent/engine/runner.py`，五阶段结构（解析→恢复→准备→主循环→完成）
- [x] 7.2 集成 StepExecutor、ConditionEvaluator、ResumeStrategy、ExecutionHooks、ExecutionObserver
- [x] 7.3 实现 on_reject 路由和 Escalation Ladder 逻辑
- [x] 7.4 确认 Runner ≤150 行（143 非空行）
- [x] 7.5 删除 `step_validator.py`（职责已被 StepExecutor 吸收，new_src 中从未存在）

## 8. 集成测试

- [x] 8.1 编写 Runner + 子模块的集成测试（完整步骤循环）
- [x] 8.2 编写 on_reject 路由的集成测试（Escalation Ladder L1-L4）
- [x] 8.3 编写断点恢复的集成测试
