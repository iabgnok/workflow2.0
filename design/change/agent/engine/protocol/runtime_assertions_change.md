# protocol/runtime_assertions.py 重构实现细节

## 一、消灭重复

_normalize_var_name 删除，改为 import protocol.utils.normalize_var_name。

## 二、接口改造（配合方向一）

现有两个函数接受 step: dict（plain dict）。重构后过渡期保持 dict 接口，方向一落地后改为接受 step: WorkflowStep（Pydantic 对象），直接访问 step.inputs / step.outputs，消灭 .get() 访问模式。[待定：接口改造时机，取决于 StepModel 在主循环里的类型确定]

## 三、可选变量判断的统一

现有实现里判断变量是否可选的逻辑：target_name.endswith("?") 和 source_name.strip().endswith("?")，两个层面都检查。重构后统一使用 protocol.utils.is_optional_var()，不再分散判断。

## 四、后置断言的严格性

现有 validate_step_outputs 检查逻辑：先看 output dict，再看 context dict，只要变量名存在于任意一处就认为通过。这个"在 context 里就算"的宽松判断是有意为之的——有些 skill 直接写 context 而不是通过返回值传递。
保持现有宽松语义，不改变。这个行为是正确的，因为 StepExecutor 会在 skill 返回 output 后立即 context.update(output)，所以后置断言时 output 里有的变量，context 里也有。只有那些 skill 直接修改 context（不通过返回值）的情况下才会出现"output 里没有但 context 里有"，这种情况也允许通过。

