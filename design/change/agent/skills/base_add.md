# skills/base.py（新增）

## 一、为什么新增这个文件

所有现有 skill 都是独立的类，各自定义 execute_step、各自在 __init__ 里调 build_chat_model，接口不统一（有的有 execute，有的只有 execute_step），幂等性和重试策略分散在 error_policy.py 的硬编码字典里。base.py 是方向三的核心：给所有 skill 提供统一的抽象接口和元数据声明点。

## 二、Skill 抽象基类

泛型基类 Skill[InputT, OutputT]（用 Generic[InputT, OutputT]），InputT 和 OutputT 是 Pydantic BaseModel 的子类型，分别代表 skill 的输入和输出契约。
抽象方法 async execute_step(step: dict, context: dict) -> dict：保持和现有 Runner 调用约定完全一致的接口，过渡期不改调用方。这不是最终形态（方向一完全落地后应该是类型化的输入输出），但当前阶段维持 dict 兼容。
类变量（子类声明元数据用）：

name: str：技能注册名，和 .step.md 里 **Action** 的值对应
description: str：一句话说明能做什么，注入 SkillCard
when_to_use: str：何时适合用，注入 SkillCard
do_not_use_when: str = ""：明确不适合的场景，注入 SkillCard（可选）
idempotency: IdempotencyLevel：幂等性等级，error_policy 通过注册表读取
retry_policy: ErrorPolicy：重试策略，error_policy 通过注册表读取
input_type: type[BaseModel] | None = None：输入 Pydantic 类型（方向一用）
output_type: type[BaseModel] | None = None：输出 Pydantic 类型（方向一用）

schema_summary() -> str 类方法：从 input_type 和 output_type 的 Pydantic schema 生成简短的文本描述，供 build_skill_manifest() 使用。如果 input_type / output_type 为 None 则返回 "（暂无类型声明）"。

## 三、LLMAgentSpec 子基类

继承 Skill，专门为 LLM 技能设计，新增：

system_prompt_path: str | None = None：Prompt 文件路径（从 prompts/ 目录读取）
user_prompt_template: PromptTemplate | None = None：LangChain PromptTemplate
default_temperature: float = 0.0：默认温度，子类可 override

_get_structured_llm(schema: type[BaseModel]) 方法：封装 LLMClientRegistry.get_or_create() + build_structured_output_model() 的调用链，子类在 __init__ 里调用一次，不再各自 build_chat_model。
_load_system_prompt() -> str 方法：如果 system_prompt_path 不为 None，从文件路径读取 system prompt 文本并缓存；否则返回空字符串。

## 四、IOSkillSpec 子基类

继承 Skill，专门为 I/O 技能（file_reader、file_writer）设计，无额外字段，只是语义分组标记。FlowSkillSpec 同理，给 sub_workflow_call 用。