# skills/llm/generator.py（从 atomic/llm_generator_call.py 迁移）

## 一、文件搬移和重命名

从 skills/atomic/llm_generator_call.py 迁移到 skills/llm/generator.py。注册名 name = "llm_generator_call" 保持。

## 二、继承 LLMAgentSpec，声明元数据

类变量声明：

name = "llm_generator_call"
description = "基于 WorkflowBlueprint 生成可执行的工作流，支持首次生成和修复重试"
when_to_use = "Planner 完成蓝图设计后，生成具体的 .step.md 工作流"
do_not_use_when = "只是评审工作流质量（用 llm_evaluator_call）"
idempotency = IdempotencyLevel.L0
retry_policy = ErrorPolicy(max_retries=2, backoff_base=2.0, action_on_exhaust=FailureAction.CONFIRM)
system_prompt_path = "prompts/generator_system_v1.md"

## 三、Prompt 改造（方向二核心）

1. GENERATOR_PROMPT_TEMPLATE 的变量名改变：当前注入 registered_skills（纯名称列表）。重构后改为注入 skill_manifest（SkillCard 结构化描述），变量名在 PromptTemplate 里从 {registered_skills} 改为 {skill_manifest}。execute_step 里从 context.get("skill_manifest") 取值（Runner __init__ 时已写入 context）。
2. system prompt 外置后的内容（prompts/generator_system_v1.md）：这个文件的内容包含：角色定义、DSL 书写规则（**Input** 单数、变量名对齐规范、on_reject 只能向前跳）、禁止发明不在白名单里的技能名的硬规定、至少两个完整的 few-shot 示例工作流。
3. retry_context 的格式改善：现有的 retry_context 只是把 prev_defects 原样拼入字符串。重构后改为结构化的格式，明确标注每条缺陷的来源（Evaluator 语义审查 vs. 协议层 Gatekeeper/DryRun 错误回流），让 LLM 能区分"语义问题"和"结构性规则违反"并分别处理。格式示例："[EVALUATOR] Step 2: 变量 x 未声明" 和 "[PROTOCOL:STEP_INPUT_UNBOUND] step:3 变量 y 不可达"。

## 四、execute_step 的最大变化：去掉文本往返

- 现有路径：
    LLM 输出 StructuredWorkflowArtifact → _render_markdown() 渲染成 Markdown 文本 → normalize_generated_artifact() 清洗 → 返回 {"final_artifact": markdown_str}。
- 重构后路径：
    LLM 输出 StructuredWorkflowArtifact → 验证 action 合法性（Gatekeeper 会做，但在这里做一次快速失败）→ 直接通过适配器转为 WorkflowModel → 返回 {"final_artifact": workflow_model}。
- _render_markdown() 的命运：逻辑搬移到 WorkflowModel.to_markdown() 方法（protocol/models.py 分析里已说明）。Generator 不再负责渲染，只负责生成结构化对象。normalize_generated_artifact() 在新路径下不再调用，只在旧路径（回放持久化文件时）保留。
- _validate_actions() 的删除：方向三落地后，WorkflowStepSpec.action 是 Literal[...] 枚举，Pydantic 结构化输出阶段就拦截了非法技能名，这个方法彻底删除。过渡期如果 Literal 枚举还没实现，保留但标注为 deprecated。
- GeneratorArtifact（旧格式）的处理：现有代码里有 isinstance(artifact, GeneratorArtifact) 的兼容判断。GeneratorArtifact 是更早版本的输出类型，已被 StructuredWorkflowArtifact 取代。重构后删除这个兼容分支，只支持 StructuredWorkflowArtifact 输出。如果 LLM 返回了旧格式（不会发生，因为 Pydantic structured output 绑定了 schema），抛明确的 ValueError。

## 五、StructuredWorkflowArtifact 的 action 字段枚举约束（方向二+三核心）

现有 WorkflowStepSpec.action: str 是普通字符串，LLM 可以填任何值。重构后改为 Literal[skill_names...] 动态枚举：SkillRegistry 在 Runner 初始化后，调用一个工厂函数 make_workflow_step_spec(skill_names: list[str]) -> type[WorkflowStepSpec] 动态生成带有 Literal 约束的 WorkflowStepSpec 类，再用这个类重新构建 StructuredWorkflowArtifact 的 schema，最后绑定给 _structured_llm。这样 Pydantic 在解析 LLM 输出时就会拦截非法技能名。[待定：动态生成 Pydantic 类的具体实现方式，Pydantic v2 支持 create_model() 动态创建]