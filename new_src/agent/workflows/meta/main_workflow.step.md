---
version: 2.0
name: Meta Main Workflow
description: Orchestrates Planner, Designer, and Evaluator into a closed loop.
inputs:
  - requirement
outputs:
  - final_artifact
---

## Step 1: Run Planner
**Action**: `sub_workflow_call`
**Workflow**: agent/workflows/meta/workflow_planner.step.md
**Input**:
- requirement
**Output**:
- workflow_blueprint

## Step 2: Run Designer
**Action**: `sub_workflow_call`
**Workflow**: agent/workflows/meta/workflow_designer.step.md
**Input**:
- workflow_blueprint
- prev_defects?
- escalation_level?
**Output**:
- final_artifact

## Step 3: Run Evaluator
**Action**: `sub_workflow_call`
**Workflow**: agent/workflows/meta/quality_evaluator.step.md
**on_reject**: 2
**Input**:
- final_artifact
- escalation_level?
- prev_defects?
**Output**:
- evaluator_report
