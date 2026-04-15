# infra/variable_mapper.py（从 engine/variable_mapper.py 搬移）

## 一、VariableMappingError 异常定义

在同文件顶部定义 class VariableMappingError(Exception): pass，不依赖外部异常类文件。

## 二、map_inputs 的必填变量校验

现有逻辑：找不到变量只打 warning，继续执行，子变量在 child_context 里缺失。
重构后：对于 value 不以 ? 结尾的映射条目（必填变量），找不到时抛 VariableMappingError(f"父上下文中不存在变量 '{parent_path}'，无法映射到子工作流变量 '{child_key}'。可用 key: {sorted(parent_context.keys())}")。错误信息包含当前 context 的 key 列表，方便调试定位哪个变量缺失。
可选变量（child_key 以 ? 结尾，如 "prev_defects?": "prev_defects"）：继续静默跳过，不报错。判断方式：检查 child_key.endswith("?")，同时把写入 child_context 时用的 key 去掉 ? 后缀。

## 三、_get_nested_value 和 _set_nested_value 的点分路径支持

这两个方法支持 user.profile.name 这样的路径访问嵌套 dict。保持不变。
但当前 context 是 flat dict，点分路径在实际工作流中极少用到（meta workflow 的变量名都是 flat 的如 workflow_blueprint、final_artifact）。这个能力保留但不是当前重构的重点。

## 四、map_outputs 的写回方式

现有 map_outputs 的输出映射格式是 {"父变量路径": "子变量路径"}，原地修改 parent_context。但 SubWorkflowCall 在 _run_sub_workflow 里既调了 map_outputs 修改 parent_context，又把结果写入 mapped_results 再合并返回——两种写法并存导致父 context 被修改了两次。
重构后统一：map_outputs 返回 dict[str, Any]（写回父 context 的变量集合）而不是原地修改，SubWorkflowCall 用返回值做 context.update()，删除原地修改模式，行为更清晰，副作用更可控。[待定：改变 map_outputs 返回值会影响 sub_workflow_call，两者需同步修改]