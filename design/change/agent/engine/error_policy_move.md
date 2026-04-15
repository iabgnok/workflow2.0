# error_policy.py 重构实现细节

## 一、整体方向

这个文件有两部分：数据定义（IdempotencyLevel、FailureAction、ErrorPolicy、DEFAULT_POLICIES、SKILL_IDEMPOTENCY）和执行函数（resolve_policy、execute_with_policy）。重构的核心变化是数据定义部分变成查询注册表，不再是硬编码字典。执行函数逻辑本身基本不变。

## 二、枚举和 dataclass

IdempotencyLevel（L0/L1/L2）：保持不变，这是核心概念定义，不依赖其他任何模块，放在这里合理。
FailureAction（RETRY/CONFIRM/ROLLBACK/SKIP）：保持不变。注意 ROLLBACK 当前没有实际实现（DEFAULT_POLICIES["DANGER"] 的 action_on_exhaust 是 ROLLBACK，但 execute_with_policy 里没有 rollback 分支），这是遗留的占位符。重构不改这个行为，但加注释说明。
ErrorPolicy dataclass：保持不变，三个字段 max_retries、backoff_base、action_on_exhaust。

## 三、DEFAULT_POLICIES 和 SKILL_IDEMPOTENCY 的去向

这两个硬编码字典是问题核心：新增一个 skill 需要同时改 error_policy.py，否则新 skill 会 fallback 到 ErrorPolicy(0, 0.0, FailureAction.CONFIRM) 这个"不重试"的默认策略，可能导致问题。
重构后，每个 AgentSpec 子类声明自己的 idempotency 和 retry_policy（见方向三的设计）。SkillRegistry 在扫描注册时，把这些元数据存在注册项里。
DEFAULT_POLICIES 和 SKILL_IDEMPOTENCY 字典保留作为 fallback，用于尚未迁移到 AgentSpec 的 skill（过渡期兼容）。但字典本身不再是权威来源。

## 四、resolve_policy() 函数

重构后的查找顺序：

先查 skill_registry.get_policy(skill_name)（如果 skill 有 AgentSpec 且声明了 policy）
找不到或 skill 没有 AgentSpec → fallback 到 DEFAULT_POLICIES.get(skill_name, ErrorPolicy(0, 0.0, FailureAction.CONFIRM))


函数签名改为 resolve_policy(skill_name: str, skill_registry: SkillRegistry | None = None) -> ErrorPolicy，允许传入 registry 实例做查询，也允许不传（测试场景或无 registry 场景）退化到字典查找。

## 五、execute_with_policy() 函数

函数签名保持不变：async execute_with_policy(skill_name, execute_func, *args, **kwargs)。
内部逻辑改一处：调用 resolve_policy 时传入 skill_registry（如果有的话）。由于 execute_with_policy 当前是全局函数，不持有 registry 引用，这里有一个设计决策：将 execute_with_policy 的调用点从全局函数改为 StepExecutor 的方法调用，StepExecutor 持有 skill_registry，自然能在调用时传入。[待定：execute_with_policy 是否保持全局函数（当前方式）还是变成 StepExecutor 的方法，倾向于后者，因为它和 StepExecutor 的其他职责高度内聚]
SkillNotFoundError 的处理：两处 except SkillNotFoundError: raise 保持，不包装。
重试日志格式保持现有的 "技能 {skill_name} 进行第 X/N 次重试" 格式，不变。