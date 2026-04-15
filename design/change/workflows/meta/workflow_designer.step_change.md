# workflows/meta/workflow_designer.step.md

## 一、现有内容评估

有两个条件步骤：Step 1 是首次生成（not prev_defects），Step 2 是修复重试（prev_defects）。这两个步骤的 condition 互斥，保证任意情况下只执行一个，逻辑是正确的。

## 二、需要调整的地方

Step 2 的 Input 声明：修复重试时需要 prev_defects 和 escalation_level，但这两个变量在第一轮不存在。在 workflow_designer 内部，这两个变量已经是由 Condition 过滤保护的——只有 prev_defects 真实存在时 Step 2 才会执行。但前置断言（RuntimeAssertions）仍然会检查声明的 Input 是否在 context 里存在，会产生误报。
解法：在 Step 2 的 Input 里也标记为可选：

markdown   ## Step 2: 修复被打回的草案
   **Action**: `llm_generator_call`
   **Condition**: prev_defects
   **Input**:
   - workflow_blueprint
   - prev_defects?
   - escalation_level?
   **Output**:
   - final_artifact
这样前置断言不会因为理论上不会到达（condition 已经保证有 prev_defects）但万一 context 里变量缺失的边界情况而崩溃。

更新 version: 2.0，去掉 description 里的 META_CREATOR_GENERATOR 前缀标签。