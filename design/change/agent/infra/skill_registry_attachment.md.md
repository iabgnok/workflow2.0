# infra/skill_registry.py（从 engine/skill_registry.py 搬移）

## 一、递归扫描实现细节

scan(skills_root: str) -> None 方法改为：

base = Path(skills_root)
for file_path in base.rglob("*.py"): 递归扫描
跳过 _ 开头的文件，跳过 base.py（基类文件）
模块名推导：用 file_path.relative_to(base.parent) 计算相对路径，替换 / 为 .，去掉 .py 后缀得到 agent.skills.llm.planner 这样的模块名

skill 注册 key 的来源：先查 cls.name（AgentSpec 声明的），回退到文件名 stem。如果两个文件 stem 不同但 cls.name 相同，后注册的覆盖先注册的，并打 warning。

## 二、build_skill_manifest() 的格式细节

对每个注册的 skill 生成如下文本块（Markdown 格式，可直接嵌入 Prompt）：

   {skill.name}
   用途：{skill.description}
   何时使用：{skill.when_to_use}
   不要用于：{skill.do_not_use_when}（如果为空则省略这行）
   输入：{input_schema_summary}
   输出：{output_schema_summary}
   {special_note}（如果有则包含）

对没有 AgentSpec 基类的旧 skill（过渡期），生成：### {name}\n用途：（暂无详细描述），不影响整体格式。
build_skill_manifest() 的返回值缓存在 self._manifest_cache: str | None = None，第一次调用时生成，之后命中缓存直接返回。register() 手动注册新 skill 后清空缓存（self._manifest_cache = None）以便下次重新生成。

## 三、_ModuleSkillAdapter 的命运

过渡期保留，专门处理没有 execute_step 方法的旧模块级函数 skill。重构完成后删除。注释里标明 # Deprecated: remove after all skills migrate to AgentSpec。