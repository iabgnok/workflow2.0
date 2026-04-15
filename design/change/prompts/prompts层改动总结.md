# prompts 层的改动总结

prompts/ 目录

整体说明
这是全新目录，来源于方向二的核心要求：把三个 LLM skill 里硬编码的 PromptTemplate 字符串外置为独立文件，使调参不动代码，且天然有版本历史（文件名带版本号）。目录下每个文件对应一个角色的 system prompt，user prompt 模板仍然保留在 skill 的 Python 文件里（因为 user prompt 需要 LangChain PromptTemplate 的变量替换机制，外置为文件后需要额外的模板引擎支持）。[待定：user prompt 是否也外置，当前阶段只外置 system prompt]

prompts/目录的加载机制：
    关于 prompts/ 目录的加载机制（补充说明）
    一、LLMAgentSpec._load_system_prompt() 的实现

    读取 system_prompt_path 对应的文件。路径解析：如果是相对路径，基准目录是 settings.PROMPTS_ROOT（默认 {project_root}/prompts/）；如果是绝对路径直接使用。
    读取结果缓存在类变量 _system_prompt_cache: str | None = None，类级别缓存（不是实例级别），同一个类的多个实例共享同一份缓存，避免重复读文件。
    文件不存在时抛 FileNotFoundError，而不是静默返回空字符串，让问题在初始化阶段暴露，不拖到运行时。

    二、Prompt 文件的 {skill_manifest} 占位符处理

    generator_system_v1.md 里有一段说明"技能白名单在每次调用时动态注入"，但文件本身是静态的，占位符 {skill_manifest} 不在文件里，而在 GENERATOR_PROMPT_TEMPLATE（user prompt 模板）里。
    system prompt 文件是纯静态文本，每次调用时不做变量替换，只是前置拼接到 LangChain 的 SystemMessage 里。动态部分（skill_manifest、blueprint、prev_defects）全部在 user prompt 模板里处理。这是 system/user 分离的核心价值：system 描述不变的规则，user 描述每次调用的具体任务。