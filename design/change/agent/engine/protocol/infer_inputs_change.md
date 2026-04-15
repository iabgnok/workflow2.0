# protocol/infer_inputs.py 重构实现细节

## 一、infer_minimal_inputs() 的行为保持

优先使用 workflow.metadata.inputs 声明的变量列表；没有声明时，从第一步的 inputs 里推断（找所有没有前置步骤产生的变量）。这个逻辑保持。
推断逻辑的精度限制：当前实现直接取所有步骤的 inputs.values() 作为候选，没有做"是否被前置步骤产生"的过滤。这意味着中间步骤依赖的变量也可能被推断为"最小输入"。已知局限性，加注释说明，不在重构中改变。

## 二、with_runtime_input_defaults() 的改造

如上所述，五个默认值改为从 settings.py 读取。函数签名和行为保持不变，只改实现细节。