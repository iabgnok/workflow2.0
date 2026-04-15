# variable_mapper.py → 移入 infra/ 重构实现细节

## 一、文件搬移和依赖修复

从 agent/engine/ 移入 agent/infra/。当前 sub_workflow_call.py（skill 层）直接 import variable_mapper（engine 层），这是 skill → engine 的反向依赖，是架构问题。搬入 infra/ 后，sub_workflow_call 改为 import agent.infra.variable_mapper，依赖方向变为 skill → infra，正确。

## 二、逻辑本身基本不变

map_inputs(parent_context, input_mapping) -> dict：保持现有实现。从父 context 按路径提取变量，深拷贝后放入子 context。
map_outputs(child_context, parent_context, output_mapping) -> None：保持现有实现。从子 context 提取变量，深拷贝后写回父 context。
_get_nested_value / _set_nested_value：保持点分路径的嵌套访问逻辑，这是子工作流 I/O 映射的核心能力。

## 三、映射失败时的行为改变

现有实现：找不到变量时只打 warning，不抛异常，子 context 里该变量缺失，子工作流第一步的前置断言会发现并报错，错误信息指向"子流程前置断言失败"而不是"变量映射失败"。
重构后：map_inputs 在找不到变量时应该根据变量是否可选来决定：

变量名不以 ? 结尾（必填）：抛 VariableMappingError(f"父 context 中不存在变量 '{parent_path}'，映射到子变量 '{child_key}' 失败")，让错误在映射阶段就暴露，不等到子流程运行时才崩
变量名以 ? 结尾（可选）：保持现有的静默跳过行为

VariableMappingError 定义在同文件内（或 engine/errors.py）。[待定：新增 engine/errors.py 统一管理引擎层异常的决策]