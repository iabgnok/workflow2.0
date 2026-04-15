# skills/llm/prompt.py（从 atomic/llm_prompt_call.py 迁移）

## 一、文件搬移和整体评估

这是最基础的通用 LLM 调用 skill，直接从 step.content 里提取 ```prompt``` 代码块作为 prompt 发送。功能简单，代码质量是所有 skill 里最粗糙的（有 print、有 Mock 模式的残留逻辑）。

## 二、继承 Skill，声明元数据

类变量：

name = "llm_prompt_call"
description = "通用 LLM 调用，从步骤内容的 ```prompt ```块中提取 prompt 并调用 LLM"
when_to_use = "需要自由格式的 LLM 调用时，prompt 模板直接写在 .step.md 步骤里"
do_not_use_when = "需要结构化输出时（用专门的 planner/generator/evaluator）"
idempotency = IdempotencyLevel.L0
retry_policy = ErrorPolicy(max_retries=2, backoff_base=3.0, action_on_exhaust=FailureAction.CONFIRM)

## 三、__init__ 改造

去掉 Mock 模式。现有代码在初始化失败时 self.client = None，在 execute 里检查并返回 Mock 输出。这个 Mock 模式是早期开发阶段的调试便利，现在反而会掩盖真实的配置问题。重构后：初始化失败直接向上传播，让 SkillRegistry 感知，不进入注册表。
使用 LLMClientRegistry.get_or_create() 替代直接 build_chat_model()，走缓存。

## 四、接口统一为 execute_step

现有只有 execute(text, context) 没有 execute_step。重构后统一接口：新增 execute_step(step, context) 作为主入口，内部从 step['content']（已经过变量注入）里提取 prompt 块，调 LLM，返回 {"llm_output": response_text}。
**```prompt```块解析**：保持现有正则r'```prompt\n(.*?)\n```'，re.DOTALL。未找到 prompt 块时改为抛 ValueError("LLMPromptCall: step.content 中未找到 ```prompt 代码块```") 而不是静默返回空 dict。
print 改为 logger：这是代码质量修复，不是功能变化。