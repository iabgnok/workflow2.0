# workflows/meta/main_workflow.step.md

## 一、现有内容评估

现有文件结构已经很规范，是所有 meta workflow 中最清晰的。三个步骤对应三个角色，on_reject: 2 在 Step 3 声明，指向 Designer 步骤，符合 DSL 规范。

## 二、需要调整的地方

prev_defects 和 escalation_level 的初始值处理：Step 2（Run Designer）的 Input 里声明了 prev_defects 和 escalation_level，但这两个变量在 meta workflow 第一轮执行时 context 里没有（Runner 会通过 context.setdefault 注入默认值 [] 和 1）。按照新的变量可选标记规范，这两个变量应该标记为可选：

markdown   ## Step 2: Run Designer
   **Action**: `sub_workflow_call`
   **Workflow**: agent/workflows/meta/workflow_designer.step.md
   **Input**:
   - workflow_blueprint
   - prev_defects?
   - escalation_level?
   **Output**:
   - final_artifact
? 标记表示这些变量可选，前置断言不会因为第一轮缺失而报错，同时 VariableMapper 映射到子工作流时也会跳过缺失的可选变量。

frontmatter outputs 的准确性：现有声明 outputs: - final_artifact，但实际上 meta workflow 完成后 context 里还有 workflow_id、evaluator_report 等。frontmatter outputs 只声明"对外暴露的主要输出"，辅助变量不列入。保持现有声明，只有 final_artifact 是真正的对外输出。
version 字段更新：从 1.0 更新到 2.0，对应重构版本。所有 meta workflow 文件都跟着更新版本号。
workflow 路径的相对路径问题：现有 **Workflow**: agent/workflows/meta/workflow_planner.step.md 是相对于项目根目录的路径。sub_workflow_call 在解析时需要把这个路径转换为绝对路径。重构后统一约定：meta workflow 里的 **Workflow**: 字段使用相对于项目根目录的路径，SubWorkflowCall 在 execute_step 里统一做 os.path.join(settings.PROJECT_ROOT, workflow_path) 转换。[待定：settings.PROJECT_ROOT 的定义和初始化]