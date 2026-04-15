# workflows/meta/quality_evaluator.step.md

## 一、现有内容评估

只有一步 llm_evaluator_call，结尾有一段 blockquote 注释说明"具体打分逻辑封装在底层 py 文件中，此处即为透明挂载"。这段注释是文档性质的，不影响引擎行为。

## 二、需要调整的地方

删除 blockquote 注释：这段注释破坏了".step.md 只做编排声明"的原则，而且说的是旧架构（"底层 py 文件"）。重构后 Prompt 外置到 prompts/evaluator_system_v1.md，这段解释更加过时。删除，保持文件只有 frontmatter + step 声明。
escalation_level 标记为可选：同 workflow_designer 的逻辑，第一轮时 escalation_level 由 Runner 默认注入为 1，但如果前置断言严格检查，会发现 step 声明了 Input 但 context 里可能没有（在理论边界情况下）。标记为可选：

markdown   ## Step 1: 四维质量门禁审查
   **Action**: `llm_evaluator_call`
   **Input**:
   - final_artifact
   - escalation_level?
   **Output**:
   - evaluator_report

更新 version: 2.0，去掉描述里的 META_CREATOR_EVALUATOR 前缀。