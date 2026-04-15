# skills/llm/planner.py（从 atomic/llm_planner_call.py 迁移）

## 一、文件搬移和重命名

从 skills/atomic/llm_planner_call.py 迁移到 skills/llm/planner.py。类名 LLMPlannerCall 保持，注册名 name = "llm_planner_call" 保持（SkillRegistry 用 AgentSpec.name 注册，和 .step.md 里的 action 名对应）。

## 二、继承 LLMAgentSpec，声明元数据

新增类变量声明：

name = "llm_planner_call"
description = "将自然语言需求解构为结构化的工作流蓝图（WorkflowBlueprint）"
when_to_use = "需要把一个复杂需求拆分成可执行步骤时，由 Meta Workflow 调用"
do_not_use_when = "需求已经是结构化蓝图，或者直接生成工作流代码"
idempotency = IdempotencyLevel.L0
retry_policy = ErrorPolicy(max_retries=2, backoff_base=2.0, action_on_exhaust=FailureAction.CONFIRM)
system_prompt_path = "prompts/planner_system_v1.md"（新增，Prompt 外置后读取）[待定：Prompt 文件路径约定]

## 三、__init__ 改造

不再直接调 build_chat_model()，改为调 self._get_structured_llm(WorkflowBlueprint)（继承自 LLMAgentSpec），走 LLMClientRegistry 缓存。
去掉 try/except 包裹的初始化逻辑（现有代码在初始化失败时把 _structured_llm 设为 None，然后在 execute_step 里再检查），改为让异常在 SkillRegistry.scan() 阶段就暴露，注册失败的 skill 不进入注册表，比静默 None 更诚实。

## 四、execute_step 改造

requirement 取值收紧：现有代码有 context.get("requirement") or context.get("user_request") 的兼容写法，还有没有值时生成"打招呼工作流"的兜底。重构后去掉兜底，requirement 必须存在于 context，否则抛 ValueError("Planner: context 中缺少 'requirement'")。前置断言（RuntimeAssertions）负责在这之前就拦截。
Prompt 构建改为支持 system prompt 外置：如果 system_prompt_path 指定了文件，先读取 system prompt，然后把 requirement 注入 user prompt。现有的 PLANNER_PROMPT_TEMPLATE 作为 user prompt 模板保留。[待定：system prompt 和 user prompt 的拼接方式，取决于 LangChain 的消息格式]
返回值：当前返回 {"workflow_blueprint": blueprint_json}，blueprint_json 是 model_dump_json() 序列化后的字符串。这是现有的序列化边界问题（方向一识别的痛点）。
重构后分两阶段：

过渡期（当前重构）：返回值保持 {"workflow_blueprint": blueprint_dict}，把 model_dump_json() 改为 model_dump()，存入 context 的是 dict 而不是 JSON 字符串，消灭 Generator 里的 json.loads 兼容处理。
方向一完全落地后：返回 {"workflow_blueprint": blueprint_object}，直接存 WorkflowBlueprint Pydantic 对象。[待定：过渡期结束时机]

## 五、WorkflowBlueprint 等 Pydantic 类的位置

现有 WorkflowBlueprint、StepBlueprint、SubWorkflowBlueprint 定义在 llm_planner_call.py 里。重构后这些类是 Planner 的输出契约，应该定义在 skills/llm/planner.py 里（紧跟 skill 定义）或提取到 skills/llm/types.py 共享类型文件。倾向于保留在同文件，因为它们只有 Planner 使用，提取没有明显收益。