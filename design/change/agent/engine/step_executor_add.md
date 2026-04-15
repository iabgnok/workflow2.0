# step_executor.py（新增，从 Runner 拆出）

## 一、为什么新增这个文件

从 Runner 分析中已经确定：Runner 的主循环里"执行单步"这件事本身是一个完整的、可独立测试的单元。当前这段逻辑嵌在 run() 的 while 循环体里，混入了 Champion 逻辑、路由逻辑、压力观测，难以单独测试。拆出后，测试"单步前置断言失败"、"skill 执行超时触发重试"、"输出变量缺失触发后置断言"这些场景不再需要启动完整的 Runner。

## 二、职责范围

StepExecutor 负责且仅负责：给定一个 step 和当前 context，执行这个 step 并返回 output。内部包含：变量注入（replace_variables）、前置断言、skill 查找与调用（含 error_policy 重试）、后置断言。不负责：条件求值、状态持久化、路由决策。

## 三、__init__

- 接受 skill_registry: SkillRegistry，必填，不提供默认值（由 Runner 注入）。
- 接受 protocol_service: ProtocolService，必填，用于调用前后置断言（validate_runtime_step_inputs / validate_runtime_step_outputs）。
- 接受可选的 template_renderer，默认使用 WorkflowParser.replace_variables 的静态方法实现（[待定：replace_variables 归属决策落定后同步更新]）。

## 四、execute(step, context) -> dict 主方法（async）

1. 变量注入：调用 replace_variables(step['content'], context) 得到 text_context，用于 llm_prompt_call 等需要渲染模板内容的 skill。注意：这一步只渲染 content 字段，不渲染 action、inputs、outputs 等结构字段，这些字段用于引擎路由，不做变量替换。
2. 前置断言：调用 protocol_service.validate_runtime_step_inputs(step, context)。抛 ProtocolRuntimeValidationError 时，直接向上传播，不在 StepExecutor 里捕获——由 Runner 的 except 块统一处理并写失败状态。
3. skill 查找：skill = skill_registry.get(step['action'])，SkillNotFoundError 直接向上传播，不捕获。
4. 执行分支：当前代码区分 hasattr(skill, 'execute_step') 和 hasattr(skill, 'execute') 两种接口。重构目标是统一成一个接口，所有 Skill 都通过 AgentSpec 基类实现 execute_step(step, context) -> dict，不再有 execute(text, context) 的旧接口形式。过渡期兼容逻辑保留，但标注为 deprecated，待旧 skill 全部迁移后删除。[待定：execute vs execute_step 接口统一时机，取决于 AgentSpec 基类落地进度]
5. 调用 execute_with_policy：output = await execute_with_policy(skill_name, skill.execute_step, step_copy, context)，step_copy 是 step.copy() 后把 content 替换为渲染后的 text_context。execute_with_policy 的调用完全委托给 error_policy 模块，StepExecutor 不关心重试细节。
6. output 归一化：output = output or {}，防止 skill 返回 None 导致后续处理崩溃。保持和现有行为一致。
7. 后置断言：调用 protocol_service.validate_runtime_step_outputs(step, output, context)。同样直接向上传播。
返回值：返回 output: dict[str, Any]。StepExecutor 不负责 context.update(output)，这一步留在 Runner 主循环里，因为更新 context 是编排层的行为。

## 五、关于日志

StepExecutor 的日志只记录单步级别的信息："技能 {skill_name} 执行完毕，输出变量: {list(output.keys())}"。Runner 负责步骤开始的日志（"[Step X] Name | 技能: action"）。两者不重叠。