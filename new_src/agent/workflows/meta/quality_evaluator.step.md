---
version: 2.0
name: Quality Evaluator
description: 独立审查并给质量守门，输出结构化评审报告。
inputs:
  - final_artifact
  - escalation_level?
  - prev_defects?
outputs:
  - evaluator_report
---

## Step 1: 四维质量门禁审查
**Action**: `llm_evaluator_call`
**Input**:
- final_artifact
- escalation_level?
- prev_defects?
**Output**:
- evaluator_report
