# infra/error_policy.py（从 engine/error_policy.py 搬移）

## 一、最终归属确定

如 engine 分析里的 [待定]，现在确定：error_policy.py 归入 infra/。理由：它的核心职责是"查询技能的重试策略"，是基础设施层的能力（查注册表），而不是控制流逻辑。StepExecutor 在 infra/ 层的 execute_with_policy 里调用，依赖方向是 engine → infra，正确。

## 二、resolve_policy 的注册表查询

函数签名：resolve_policy(skill_name: str, skill_registry: AbstractSkillRegistry | None = None) -> ErrorPolicy。
查找顺序：

如果 skill_registry 不为 None：调 skill_registry.get_policy(skill_name)，返回 AgentSpec 声明的 retry_policy
返回 None（skill 不是 AgentSpec，或没有声明 policy）：fallback 到 DEFAULT_POLICIES.get(skill_name, ...)
DEFAULT_POLICIES 里也没有：返回默认 ErrorPolicy(max_retries=0, backoff_base=0.0, action_on_exhaust=FailureAction.CONFIRM)（不重试，等人工干预）

同样，SKILL_IDEMPOTENCY 的查找顺序类似：先查 AgentSpec 的 idempotency 属性，fallback 到字典，fallback 到 L2（最保守）。

## 三、execute_with_policy 归属

最终确定：execute_with_policy 不作为独立全局函数，而是变成 StepExecutor 的方法 _execute_with_policy。原因：StepExecutor 持有 skill_registry，能自然传入 resolve_policy；而全局函数需要额外参数传 registry，或者维护一个全局状态。StepExecutor._execute_with_policy(skill_name, execute_func, *args) 内部调 resolve_policy(skill_name, self.skill_registry)。
error_policy.py 里保留：枚举类、dataclass、DEFAULT_POLICIES、SKILL_IDEMPOTENCY、resolve_policy（工具函数）。删除 execute_with_policy（移入 StepExecutor）。