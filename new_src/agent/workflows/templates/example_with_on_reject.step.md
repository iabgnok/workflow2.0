---
version: 2.0
name: Example With On Reject Workflow
description: 带 on_reject 循环的少样本示例：Generator → Evaluator 闭环，支持可选变量与升级策略。
inputs:
  - requirement
  - prev_defects?
  - escalation_level?
outputs:
  - final_artifact
---

## Step 1: 生成草案
**Action**: `llm_generator_call`
**Input**:
- requirement
- prev_defects?
- escalation_level?
**Output**:
- final_artifact

## Step 2: 质量评估
**Action**: `llm_evaluator_call`
**on_reject**: 1
**Input**:
- final_artifact
- escalation_level?
**Output**:
- evaluator_report
- prev_defects
