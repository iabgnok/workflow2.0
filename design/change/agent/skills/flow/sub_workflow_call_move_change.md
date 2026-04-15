# skills/flow/sub_workflow_call.py（从 atomic/sub_workflow_call.py 迁移）

## 一、文件搬移

从 skills/atomic/ 迁移到 skills/flow/。

## 二、依赖修复（最重要）

现有代码直接 from agent.engine.variable_mapper import VariableMapper，是 skill → engine 的反向依赖，必须修复。重构后改为 from agent.infra.variable_mapper import VariableMapper，依赖方向变为 skill → infra，正确。

## 三、继承 FlowSkillSpec，声明元数据

类变量：

name = "sub_workflow_call"
description = "调用已注册的子工作流，在隔离的上下文里执行，按 Input/Output 声明映射变量"
when_to_use = "需要复用已有工作流，或将复杂流程拆分为子模块时"
special_note = "步骤必须声明 **Workflow**: <path> 字段指定子工作流路径" —— 这条信息写入 SkillCard，注入 Generator Prompt，避免 LLM 生成 sub_workflow_call 步骤时忘记写 Workflow 字段
idempotency = IdempotencyLevel.L0（子工作流的幂等性由子工作流自身的 skill 决定，这里标 L0 是说"调用行为本身是幂等的"）

## 四、execute 向后兼容方法

现有 execute 方法直接 raise ValueError，禁止通过 execute 调用。保持这个行为，不变。

## 五、execute_step 的输入变量映射校验改造

现有的 _run_sub_workflow 在调用 VariableMapper.map_inputs 时，如果父 context 里缺少必要的映射变量，只打 warning 继续执行，子工作流第一步前置断言才会崩。
重构后 VariableMapper.map_inputs 会对必填变量缺失抛 VariableMappingError（engine/infra 分析里已设计），SubWorkflowCall.execute_step 捕获这个异常并重新包装为 ValueError，错误信息指向"子工作流 X 的输入变量 Y 在父上下文中不存在"，比"子工作流前置断言失败"更清晰。

## 六、子 Runner 创建时的 hooks 处理

现有代码 Runner(filepath=workflow_path, initial_context=child_initial_context) 不传 hooks，子工作流的 Runner 实例是"干净"的，没有 Champion 相关逻辑。这个行为明确保留，子工作流运行时 ChampionTracker 不介入，是正确的设计。注释里明确说明这是故意的，不是遗漏。

## 七、返回值中的 __sub_workflow_status__ 和 __sub_run_id__

现有实现在返回 dict 里额外包含 __sub_workflow_status__: "success" 和 __sub_run_id__: run_id。这两个以双下划线开头的 key 是内部元数据。
重构后这两个 key 改为约定前缀 _meta_ 开头（_meta_sub_workflow_status、_meta_sub_run_id），和 StateStore 的 META_KEY_PREFIX 约定对齐，持久化时会被分到 meta 层。这是小的清洁性改动，但有助于三层分离后的 context 管理。[待定：meta key 前缀约定是否统一到 __（现有约定）还是 _meta_]