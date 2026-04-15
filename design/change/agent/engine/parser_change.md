# parser.py 重构实现细节

## 一、职责重新定界（最重要）

重构后 Parser 的定位发生根本性变化：只处理人工手写的 .step.md 文件，不处理 LLM 生成物。
这意味着：

    1. meta/ 目录下的工作流（main_workflow.step.md、workflow_planner.step.md 等）走 Parser 路径，因为它们是人工维护的
    2. LLM 生成物（GeneratorSpec 输出的 WorkflowModel）直接是 Pydantic 对象，经过协议层适配器转换后写入 dev/，不经过 Parser
    3. dev/ 目录下已持久化的 .step.md 文件（用于回放）依然走 Parser，因为它是从 WorkflowModel 渲染出来的文件，格式是受控的

Parser 现有的所有修复性代码（normalize_generated_artifact、sanitize_artifact_for_engine 等在 normalizer.py 里的清洗逻辑）在新架构下的价值大幅降低，因为 LLM 生成物不再流经 Parser。但不能立即删除，因为回放路径仍然需要解析已持久化的 .step.md。

## 二、WorkflowParser.__init__

1. 只接受 filepath: str，不变。内部存 self.filepath，不提前读文件（和现在一样，parse() 调用时才读）。
2. 不做任何格式假设，不做预处理。

## 三、parse() 方法

1. 文件读取：保持现有逻辑，FileNotFoundError 抛 WorkflowParseError，其他异常也包装成 WorkflowParseError。编码固定 utf-8。
2. YAML frontmatter 解析：保持现有正则 r'^---\s*\n(.*?)\n---\s*\n'，re.DOTALL，yaml.safe_load。解析失败抛 WorkflowParseError。没有 frontmatter 时 metadata = {}，content_without_frontmatter = self.raw_content。
3. 步骤块切割：保持现有 re.split(r'(?m)^## Step\s+\d+', ...) 的方式。raw_steps[0] 是 preamble 忽略，从 index 1 开始。
4. parse() 返回值：继续返回 dict（{'metadata': ..., 'steps': [...]} 这个 plain dict），不变。因为 parse() 的直接调用方是 ProtocolService.parse_workflow_file()，由 ProtocolService 负责把这个 dict 转成 WorkflowModel。Parser 不感知 Pydantic，保持职责清晰。
5. 步骤 id 分配策略：当前是 enumerate(raw_steps[1:], 1)，id 从 1 开始顺序分配，和切割顺序一致。这个逻辑保持不变。注意：id 是 Parser 分配的顺序号，不是从 Markdown 文本里解析的——.step.md 里写的是 ## Step 1 这样的标题，但数字只用于人类阅读，Parser 用 enumerate 重新分配，避免手写文件里步骤号不连续导致的问题。这个行为保持不变，但需要在注释里明确说明。

## 四、私有解析方法

1. _extract_step_name()：保持现有逻辑，取步骤块第一行冒号后的部分。边界情况：第一行没有冒号时返回整行 strip 后的内容。不变。
2. _extract_action()：保持两阶段逻辑：先尝试严格的反引号提取 `action_name`，失败再用通用 markdown scalar 提取。清理 [CONFIRM]、[DANGER] 标记（用 regex 去除行尾的这两个标记）。找不到返回 "unknown"。这个 "unknown" 是 Gatekeeper 会硬拒绝的值，不是正常值，所以返回它是合理的 sentinel。
3. _extract_workflow()：提取 __Workflow__: path/to/file.step.md，返回字符串或 None。不变。
4. _extract_condition()：提取 __Condition__: expression，返回字符串或 None。不变。
5. _extract_on_reject()：提取 __on_reject__: N，直接返回 int 或 None。这里有一个重要的保持：当前实现已经修复了原版返回字符串的类型不一致问题，重构后继续返回 int，和 WorkflowModel.StepModel.on_reject: int | None 类型对齐。
6. _extract_io()：提取 __Input__: 或 __Output__: 下的变量列表，支持两种格式：
    简单变量名：- var_name → {"var_name": "var_name"}（key 和 value 相同，表示自映射）
    键值映射：- child_var: parent_var → {"child_var": "parent_var"}
返回 dict[str, str]，不变。行内注释（# 注释）用正则清理掉，不进入变量名。__Inputs__（复数）的兼容匹配（regex 里的 s?）保留，因为 Parser 处理的是手写文件，写错了也要容忍，Gatekeeper 会在校验阶段拒绝并报告 STEP_INVALID_IO_HEADER。

## 五、replace_variables() 静态方法

1. 这个方法是否还留在 Parser 里：需要决定。当前 Runner 在执行每步前调用 self.parser.replace_variables(step['content'], self.context) 把 {{var}} 占位符替换进步骤的 content 文本，用于 llm_prompt_call 这类需要渲染模板内容的 skill。
重构后这个方法的归属有两个选项：
    - 保留在 Parser 里，Runner（或 StepExecutor）通过 parser.replace_variables() 调用
    - 移到 engine/utils.py 作为独立函数，和 Parser 解耦

倾向于移到 StepExecutor 内部或独立的 TemplateRenderer，因为"变量替换"是执行阶段的行为，和"文件解析"是两件不同的事。Parser 解析文件只做一次，变量替换在每步执行时做。[待定：replace_variables 最终归属，Parser 静态方法 vs StepExecutor 内部 vs 独立工具函数]
2. replace_variables() 的逻辑本身：保持现有实现，这是 V4 已经修复过的版本，逻辑是正确的：

    - 用 re.sub 一次性扫描，避免二次替换
    - dict/list 类型序列化为 JSON 字符串
    - 未找到的占位符静默替换为空字符串（降级容错），不抛异常
    - 变量名规则：[a-zA-Z_][a-zA-Z0-9_.] 支持点分路径如 {{user.name}}（但当前 context 是 flat dict，点分路径实际上不工作，只是 regex 允许）[待定：是否支持点分路径的嵌套 context 访问，还是明确禁止，变量名只允许 [a-zA-Z_][a-zA-Z0-9_]*]

## 六、需要新增的方法（回放路径支持）

1. 静态方法 render_workflow_model(model: WorkflowModel) -> str（[待定]）：重构后 Generator 输出 WorkflowModel Pydantic 对象，WorkflowRegistry 在持久化时需要把它渲染成 .step.md 文件写入 dev/ 目录（供人类阅读和回放用）。这个渲染逻辑当前在 LLMGeneratorCall._render_markdown() 里，应该搬到 Parser（或一个新的 WorkflowSerializer）里，作为 WorkflowModel → Markdown 文本 的标准实现。Parser 是"理解 .step.md 格式"的唯一权威，序列化也应该在这里。[待定：是否在 Parser 里新增 render_from_model() 静态方法，还是新建 WorkflowSerializer]

## 七、不变的部分和可以删除的部分

1. WorkflowParseError 异常类：保留，不变。
2. _extract_markdown_scalar() 静态工具方法：保留，不变，被_extract_action、_extract_workflow、_extract_condition 共用。
3. 不再需要的内容：当前 Parser 被 normalizer.py 里的 sanitize_artifact_for_engine() 和 normalize_generated_artifact() 配合使用，这两个函数是为了修复 LLM 生成物的格式问题。重构后 LLM 生成物不走 Parser，这两个函数的存在价值仅剩"回放路径下解析已持久化的 dev/ 文件"。由于 dev/ 的文件是从受控的 WorkflowModel 渲染出来的，格式是标准的，normalizer 的大部分 patch 逻辑不再被需要。但这部分清理应该在 Generator 结构化路径完全打通后再做，不在本次重构第一步。
