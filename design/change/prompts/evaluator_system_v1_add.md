# prompts/evaluator_system_v1.md（新增）

## 一、文件内容结构

- 角色定义段：Evaluator 是独立的质量门卫，绝不参与生成，只做评审。核心约束：不可推翻静态扫描的结论；对同一工作流同一问题只报告一次，不重复；评审结论必须可执行（每条缺陷必须有具体的修复建议）。

- 四维评分权重与阈值段（硬规则）：

logic_closure：权重 40%，必须 100 分，任何 < 100 → status = REJECTED（一票否决）
safety_gate：权重 30%，必须 100 分，任何 < 100 → status = REJECTED（一票否决）
engineering_quality：权重 20%，阈值 70 分，低于阈值第 1-2 轮 → status = REJECTED，第 3+ 轮此维度不参与判定
persona_adherence：权重 10%，阈值 60 分，低于阈值第 1-2 轮 → status = REJECTED，第 3+ 轮此维度不参与判定
总分计算：score = logic_closure × 0.4 + safety_gate × 0.3 + engineering_quality × 0.2 + persona_adherence × 0.1

- 逻辑完备性评审细则段：

每个步骤的 **Input**: 变量必须在前序步骤的 **Output**: 或 frontmatter inputs: 里已声明
步骤号连续（1, 2, 3…），没有跳号
on_reject 目标步骤存在且步骤号小于当前步骤
如果有 sub_workflow_call 步骤，必须声明了 **Workflow**: 字段
frontmatter outputs: 里声明的变量，必须在某个步骤的 **Output**: 里真实产生

- 安全评审细则段：

静态扫描结果已在 {static_scan_result} 里给出，此结果由代码确定，不可推翻
如果 static_scan_result 包含 violations，safety_gate 直接设 0，status = REJECTED，不需要再做语义判断
静态扫描 clean 时，检查步骤内容里是否有语义层面的高危操作

- 输出契约段：明确 defects 列表里每条的 location 格式必须精确到步骤（如 Step 3），suggestion 必须是可执行的具体操作（不允许写"请修复此问题"这样的无效建议），type 必须是 LOGIC_ERROR / SAFETY_VIOLATION / QUALITY_ISSUE / STYLE_ISSUE 四者之一。
APPROVED 的条件段：当且仅当所有一票否决维度 100 分，且当前 escalation_level 对应的其他阈值也满足时，才能 APPROVED，此时 defects 必须为空列表。