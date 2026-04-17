---
version: 2.0
name: Workflow Planner
description: 生成多代理工作流的结构拆分蓝图。
inputs:
  - requirement
outputs:
  - workflow_blueprint
---

## Step 1: LLM Planner Agent
**Action**: `llm_planner_call`
**Input**:
- requirement
**Output**:
- workflow_blueprint
