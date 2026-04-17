---
version: 2.0
name: Workflow Designer
description: 开发基于架构蓝图的精确可执行 .step.md 剧本。
inputs:
  - workflow_blueprint
  - prev_defects?
  - escalation_level?
outputs:
  - final_artifact
---

## Step 1: 首次全量生成
**Action**: `llm_generator_call`
**Condition**: `not prev_defects`
**Input**:
- workflow_blueprint
**Output**:
- final_artifact

## Step 2: 修复被打回的草案
**Action**: `llm_generator_call`
**Condition**: prev_defects
**Input**:
- workflow_blueprint
- prev_defects?
- escalation_level?
**Output**:
- final_artifact
