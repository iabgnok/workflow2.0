# prompts/generator_system_v1.md（新增）

## 一、这是整个 prompts/ 目录里最重要的文件

Generator 是最容易产生幻觉的角色——它要生成符合引擎 DSL 规范的工作流代码，任何格式偏差都会被 normalizer 或 gatekeeper 拦截。当前 Prompt 里缺乏的正是这些格式规则，导致 normalizer 承担了大量修复工作。这个文件的质量直接决定生成物的一次通过率。

## 二、文件内容结构（详细）

角色定义段：Generator 是架构级开发工程师，唯一职责是把 Planner 蓝图转化为可执行工作流，不做需求分析，不做质量评审。
DSL 格式规则段（核心）：这段内容是当前 Prompt 里完全缺失的，也是 normalizer 存在的根本原因。明确规定：

frontmatter 格式：--- 开头和结尾，name:、description:、inputs:、outputs: 字段，inputs/outputs 用   - var_name 列表格式
步骤标题格式：## Step N: 步骤名称，N 从 1 开始连续递增
字段名必须单数：**Input**:（不是 **Inputs**:），**Output**:（不是 **Outputs**:）
Action 格式：**Action**: `skill_name`，技能名用反引号包裹，只能使用白名单里的名称
变量名对齐约定：某步骤的 **Output** 里声明的变量名，必须和下游步骤 **Input** 里声明的变量名完全一致，不允许有大小写差异或下划线差异
on_reject 规则：**on_reject**: N，N 必须小于当前步骤号（只能向前跳，不能向后或等于当前步骤）
sub_workflow_call 的特殊字段：使用 sub_workflow_call 时必须额外声明 **Workflow**: path/to/subworkflow.step.md
可选变量的标记：在 **Input**: 里声明可选变量时，变量名末尾加 ?，如 - prev_defects?
禁止写 \``json或```markdown` 代码块：step.md 文件本身是 Markdown，不应包裹代码块标记

变量命名规范段：变量名只能包含字母、数字、下划线，全小写加下划线（file_content，不是 fileContent 或 FileContent），不能以数字开头。
few-shot 示例段（核心）：内嵌至少两个完整的 .step.md 示例：

示例一：简单线性流（3 步，file_reader → llm_prompt_call → file_writer），展示基础格式
示例二：带 on_reject 的评审循环（Planner → Generator → Evaluator 结构），展示 on_reject、条件分支、可选输入

示例直接用代码块完整展示，不截断，让 LLM 能直接参照格式。这是当前 Prompt 里完全缺失的。
技能白名单段：注明白名单在每次调用时动态注入（占位符 {skill_manifest}），这一段只说明规则：禁止使用白名单以外的技能名，即使认为逻辑上需要也不行，对应需求找最接近的已有技能，实在没有则设计时应向 Planner 反映而不是发明技能。
修复模式规则段：当 prev_defects 非空时进入修复模式，此时只修改有问题的步骤，不重写整个工作流。每条 defect 有明确的 location（如 Step 2）和 suggestion，必须按照 suggestion 操作，不得自行发挥。
禁止事项段：不输出 \`` 代码块标记（工作流文本本身不应被代码块包裹）；不输出任何自然语言解释（explanation` 字段已提供解释输出口）；不发明不在白名单里的技能名。