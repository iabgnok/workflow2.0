# prompts/planner_system_v1.md（新增）

## 一、这个文件存放什么

存放 Planner 角色的 system prompt。当前 llm_planner_call.py 的 PLANNER_PROMPT_TEMPLATE 把角色描述和任务指令混在一个 PromptTemplate 字符串里，没有区分 system 和 user 两个层次。重构后拆分：

system prompt（本文件）：角色定位、能力边界、不变的行为约束。写一次，除非角色定义本身需要调整，不随任务变化。
user prompt（保留在 planner.py）：每次调用时注入的具体 {requirement}，由 PLANNER_PROMPT_TEMPLATE 承载。

## 二、文件内容结构

角色定义段：说明 Planner 是谁、职责边界是什么。明确写出"你只负责宏观架构解构，不参与具体实现"，和"你的输出是结构化的 WorkflowBlueprint，不是 Markdown 文本"。
拆分判断标准段：明确写出触发 should_split = true 的条件——当一组步骤的输入完全来自外部、输出只被外部消费、形成完整逻辑闭环时。同时说明不应该过度拆分（超过 7 步主流程才考虑拆分子流程，少于等于 7 步直接平铺）。
输出字段约定段：列出 WorkflowBlueprint 的每个字段及其填写规范。尤其是：workflow_name 用大驼峰下划线命名（如 News_Crawler_Workflow）；handoff_contracts 描述父子流程的变量交接规范；main_flow_steps 里每步的 action_type 必须使用真实存在的技能名。
禁止事项段：不输出任何 Markdown 正文；不参与步骤内部实现细节；不输出 steps 里具体的代码逻辑。

## 三、版本管理约定

文件名带版本号 _v1。修改时新建 planner_system_v2.md，planner.py 的 system_prompt_path 指向新版本。旧版本文件保留一段时间（方便对比和回退），确认新版本稳定后再清理。
文件内顶部加一行注释说明版本意图：<!-- v1: 初始版本，基于 V4 重构 -->。