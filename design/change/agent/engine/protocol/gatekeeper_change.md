# protocol/gatekeeper.py 重构实现细节

## 一、消灭重复的 _normalize_name

删除文件内的 _normalize_name 和 _extract_metadata_inputs，改为从 protocol.utils import normalize_var_name 和 extract_metadata_inputs。整个文件内部的调用点对应修改。

## 二、action 合法性检查的唯一性确立

现有 validate_workflow() 里已有 action 白名单检查（WF_UNKNOWN_ACTIONS），这是正确的位置。
security_scan.py 里的 _scan_action_whitelist() 做的是同一件事但在文本层面用正则匹配，现在两处并存。重构后：删除 security_scan._scan_action_whitelist()，scan_artifact_security() 函数的 registered_skills 参数去掉，action 合法性完全由 gatekeeper 承担。security_scan 只做它擅长的——危险关键词和确认关键词的扫描。
LLMGeneratorCall._validate_actions() 同样做 action 合法性检查，这是第三个重复点。重构后 Generator 直接输出 WorkflowModel，在送入协议层校验之前就已经通过 Pydantic Literal[...] 枚举约束了 action 字段，_validate_actions() 可以删除。

## 三、validate_workflow() 的检查顺序

现有检查顺序：空步骤检查 → 逐步遍历（IO 标题、重复 id、on_reject、action、outputs、inputs 模板残留、inputs unbound）→ action 白名单（所有步骤汇总）。
重构后调整顺序：action 白名单检查提前到逐步遍历里，和 STEP_INVALID_ACTION 检查放在同一个步骤块里。理由：按步骤分批报错比最后汇总报错对 Generator 修复更友好（能直接定位是哪个步骤用了未注册 skill）。WF_UNKNOWN_ACTIONS 错误码保留，但 location 改为 f"step:{step.id}" 而不是全局 None。

## 四、STEP_INVALID_IO_HEADER 检查的调整

现有实现在 content 文本里搜索 "**Inputs**:" 字符串。重构后 LLM 生成物不再经过这里（走结构化路径），但手写文件仍然走 Parser → Normalizer → Gatekeeper 路径。
Normalizer 里的 normalize_generated_artifact 已经做了 **Inputs**: → **Input**: 的替换，所以到 Gatekeeper 时应该已经清洗过了。但手写文件的 Normalizer 路径不一定做这个替换（normalize_parsed_data 不做这个清洗）。
保留这个检查，它是最后防线。如果人工写的 .step.md 不小心写成了复数，在注册时会被 Gatekeeper 拦截，有明确的错误信息和修复建议，是合理的行为。

## 五、协议层错误回流到 Generator（新增能力）

这是纲领文档 P0 级别的新增能力。当 Gatekeeper 校验失败时，ProtocolReport 的 errors 需要能被 Generator 修复循环消费。
具体机制：ProtocolReport 已有 to_audit_dict() 方法，WorkflowRegistry.register_workflow_model() 失败时返回包含 protocol_report 的结构。ChampionTracker.on_workflow_complete() 在注册失败时，把 protocol_report.issues 里的 error 信息格式化后合并进 prev_defects，触发 Generator 的下一轮修复。这个合并格式要和 EvaluatorReport.defects 的格式对齐，让 Generator Prompt 能统一处理。
ProtocolIssue 需要新增 to_defect_dict() -> dict 方法，输出和 Defect（llm_evaluator_call.py 里的 Pydantic 类）格式兼容的结构：{"location": issue.location, "type": "PROTOCOL_ERROR", "reason": issue.message, "suggestion": issue.suggestion}。