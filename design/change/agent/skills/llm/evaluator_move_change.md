# skills/llm/evaluator.py（从 atomic/llm_evaluator_call.py 迁移）

## 一、文件搬移和重命名

注册名 name = "llm_evaluator_call" 保持。

## 二、继承 LLMAgentSpec，声明元数据

类变量：

name = "llm_evaluator_call"
description = "对 Generator 生成的工作流草案执行四维质量门禁，输出结构化评审报告"
when_to_use = "Generator 完成工作流生成后，进行质量审查"
idempotency = IdempotencyLevel.L0
retry_policy = ErrorPolicy(max_retries=2, backoff_base=2.0, action_on_exhaust=FailureAction.CONFIRM)
system_prompt_path = "prompts/evaluator_system_v1.md"

## 三、静态扫描与 final_artifact 的输入类型变化

当前实现：_static_scan(artifact: str) 接受 Markdown 文本字符串，调 scan_artifact_security(artifact, registered_skills)。
重构后：final_artifact 在 context 里是 WorkflowModel 对象（Generator 结构化路径落地后）。_static_scan 改为接受 WorkflowModel，调 security_scan.scan_workflow_model(model)。过渡期兼容两种：检查 final_artifact 是 str 还是 WorkflowModel，分别调用不同的扫描函数。[待定：过渡期兼容时机]
静态扫描命中直接 REJECTED 的逻辑：完全保留，这是"静态扫描优先"原则的核心实现，不改变。

## 四、Prompt 改造（方向二核心）

EVALUATOR_PROMPT_TEMPLATE 已有基础：现有 Prompt 里已有四维评分标准和判定规则（logic_closure < 100 → REJECTED 等），这部分已经是显式 rubric，方向正确。
需要强化的地方：

静态扫描命中时"你不得推翻静态规则"的约束已有，但应更强硬：如果 static_scan_result 包含 violations，在 Prompt 里直接写明 "以下违规已由代码确认，你无需判断，直接将 safety_gate 设为 0 并 REJECTED"。
把四维的权重百分比（40%/30%/20%/10%）和阈值（100/100/70/60）从 Prompt 文本移到 prompts/evaluator_system_v1.md 里单独维护，方便调参不改代码。
escalation_level 的降级规则（第 3 轮放宽）已有，保留但迁移到 system prompt 文件里。

final_artifact 传入 Prompt 的形式：当 final_artifact 是 WorkflowModel 对象时，Prompt 里需要的是其 Markdown 文本表示（供 LLM 阅读）。workflow_model.to_markdown() 提供这个转换，Evaluator 在构建 Prompt 时调用。

## 五、Defect 和 EvaluatorReport 的位置

Defect 和 EvaluatorReport 是 Evaluator 的输出契约，但同时也被 Runner（_parse_evaluator_report）、ChampionTracker（_update_champion）、协议层（错误回流格式对齐）使用。
重构后这两个类的定义位置有两个选项：

继续放在 skills/llm/evaluator.py 里，其他模块 import 这里
提取到 protocol/models.py 或独立的 skills/llm/types.py

倾向于提取到 skills/llm/types.py（新增），理由：Defect 和 EvaluatorReport 的使用范围已经超出了单个 skill，它们是跨模块的数据契约。protocol/models.py 不合适（protocol 层不应该依赖 skill 层的 LLM 输出类型）。[待定：最终位置]