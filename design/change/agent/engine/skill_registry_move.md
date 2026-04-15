# skill_registry.py → 移入 infra/ 重构实现细节

## 一、文件搬移
skill_registry.py 从 agent/engine/ 移入 agent/infra/。理由：它是一个"能力目录"，是基础设施，不是执行控制流。SkillNotFoundError 定义也随之移动，保持在同文件。

## 二、scan() 方法改为递归扫描

现有实现只扫描 skills_dir/*.py（单层），新目录结构是 skills/llm/、skills/io/、skills/flow/ 三个子目录。
改为 base_path.rglob("*.py") 递归扫描，跳过 _ 开头的文件（__init__.py、_base.py 等）。
模块名推导规则改变：现有实现用硬编码的 f"agent.skills.atomic.{skill_name}" 前缀。重构后根据相对路径动态推导：skills/llm/generator.py → agent.skills.llm.generator，skills/io/file_reader.py → agent.skills.io.file_reader。用 importlib.util 根据文件路径和 agent.skills 根路径计算相对模块名。
skill 注册的 key（name）来源：优先用 AgentSpec.name 属性（如 "llm_generator_call"），回退到文件名 stem（"generator"）。保证注册 key 和 .step.md 里 **Action** 声明的名字一致。[待定：AgentSpec 基类落地后同步确认 name 属性约定]

## 三、_build_instance() 方法改为 AgentSpec 优先

新的查找顺序：

先找继承 AgentSpec 的类（issubclass(cls, AgentSpec) and cls is not AgentSpec），优先实例化
找不到再回退到现有的 execute_step / execute 方法探测逻辑（过渡期兼容）
_ModuleSkillAdapter 在新架构下不再需要，但过渡期保留

## 四、新增 build_skill_manifest() 方法

这是为 Generator Prompt 的 SkillCard 注入设计的核心方法。遍历 _registry 里的所有注册项，对每个 skill：

如果是 AgentSpec 实例：读取 name、description、when_to_use、do_not_use_when、input_type.schema_summary()、output_type.schema_summary()
如果不是 AgentSpec（旧 skill 过渡期）：只提供名字和"暂无详细描述"占位

输出是一段结构化的文本字符串（Markdown 格式），直接可注入 Prompt：

```
   file_reader
   用途：读取本地文件内容，返回文本字符串
   何时使用：需要读取文件、配置时
   不要用于：写入或删除文件
   输入：file_path: str（必填）
   输出：file_content: str；error: str（可选）
```

build_skill_manifest() 是同步方法，在 Runner __init__ 时调用一次，结果缓存到 self._manifest: str，之后通过 get_manifest() 读取。不需要每次重新生成。

## 五、新增 get_policy() 方法（配合 error_policy 重构）

get_policy(skill_name: str) -> ErrorPolicy | None：如果注册的 skill 是 AgentSpec 实例，返回 spec.retry_policy；否则返回 None（让 error_policy 的 fallback 字典接管）。

## 六、SkillNotFoundError 的错误信息改善

现有错误信息："技能 '{name}' 未注册。已注册技能: {self.get_names()}"。保持这个格式，但新增一条信息："如需使用此技能，请在 agent/skills/ 下创建对应的 AgentSpec 类并确保 SkillRegistry 能扫描到。"，帮助开发者快速定位问题。