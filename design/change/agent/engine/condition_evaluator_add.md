# condition_evaluator.py（新增，从 Runner 拆出）

## 一、为什么新增这个文件

条件求值当前内联在 Runner 主循环里，用到了 simpleeval 的三个异常类型。这个逻辑单独可测，而且未来可能需要扩展（比如支持更复杂的表达式语法，或者需要在求值失败时提供更好的诊断信息）。拆出后可以针对 condition_evaluator 独立写测试，覆盖各种边界：变量未就绪、表达式非法、布尔值边界等。

## 二、ConditionEvaluator 的接口

无状态，所有方法可以是静态方法或类方法，也可以直接设计成模块级函数，用 class 包裹只是为了命名空间整洁。[待定：是否需要 class 还是直接模块级函数，取决于后续是否有配置注入需求，比如自定义函数白名单]
核心方法：eval(condition: str | None, context: dict) -> tuple[bool, str]，返回 (should_skip, reason)。

condition 为 None 或空字符串：返回 (False, "") 表示不跳过，直接执行。
simpleeval.simple_eval(condition, names=context) 返回 falsy 值：返回 (True, f"条件不满足: {condition}")。
NameNotDefined 异常：返回 (True, f"条件变量未就绪: {e}")——语义上等同于条件不满足，跳过步骤。这个行为继承自现有实现，是经过 V4 确认的设计决策，不改变。
InvalidExpression 异常：返回 (False, f"条件表达式非法: {e}，默认执行")——非法表达式不跳过，打 warning，继续执行。这个"宽容"行为也继承自现有实现。
返回值为 truthy：返回 (False, "") 表示不跳过。

Runner 主循环里调用：skip, reason = condition_evaluator.eval(step.condition, context)，if skip: log(reason); current_step_index += 1; continue。消灭了现有代码里三段分散的 try/except/continue。