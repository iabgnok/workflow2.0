# templates 目录的说明

workflows/templates/ 目录（新增）

## 一、这个目录的用途

存放标准的 .step.md 模板文件，服务两个场景：

作为 Generator system prompt 里 few-shot 示例的文件形式存储，prompts/generator_system_v1.md 里的示例可以 include 或内联这些文件（[待定：Prompt 文件是否支持 include 机制，还是每次生成 SkillManifest 时动态读取文件内容并嵌入 Prompt]）
作为手工开发新工作流时的参照模板

## 二、templates/example_linear.step.md（新增）

这是 Generator few-shot 示例一：最简单的三步线性流，展示基础格式。内容设计原则：

frontmatter 完整（name、description、inputs、outputs 都有）
三个步骤用到三种不同的基础技能（file_reader、llm_prompt_call、file_writer）
变量命名规范（全小写下划线）
步骤间变量传递清晰（Step 1 的 output file_content 是 Step 2 的 input）

实际内容和现有 hello_world.step.md 基本一致，但做了以下清洁：

去掉 hello_world.step.md 里 Step 2 末尾多余的 ` 代码块标记（现有文件有一个 Context from file: {{file_content}} 残留行，是格式问题）
统一使用 **Input**:（单数）
确保所有变量名在步骤间一致

## 三、templates/example_with_on_reject.step.md（新增）

这是 Generator few-shot 示例二：带 on_reject 评审循环的三步流，展示更复杂的 DSL 特性。内容设计：

三步结构：Step 1 生成内容（llm_prompt_call）→ Step 2 条件生成（首次，condition: not prev_feedback）→ Step 3 Evaluator（llm_evaluator_call，有 on_reject: 2）
展示 on_reject 字段的正确写法（步骤号小于当前步骤号）
展示可选变量标记（- prev_feedback?）
展示 Escalation 相关变量的传递（escalation_level?）

这个示例的价值：让 Generator 直接看到"如何构建一个有反馈循环的工作流"，而不是从 DSL 规则描述里自行推断。

## 四、templates/ 目录不进入 SkillRegistry 扫描

templates/ 是 .step.md 文件，不是 Python 模块，SkillRegistry 扫描的是 skills/ 目录下的 .py 文件，两者完全不干扰。
WorkflowRegistry 的注册流程也不扫描 templates/，这里的文件不会自动进入 index.json。只有通过 register_generated_workflow() 或 register_workflow_model() 显式注册才会写入索引。