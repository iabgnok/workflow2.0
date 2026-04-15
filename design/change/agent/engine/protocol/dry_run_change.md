# protocol/dry_run.py 重构实现细节

## 一、消灭重复

删除文件内的 _normalize_name、_is_optional_source、_extract_metadata_inputs，改为从 protocol.utils import。

## 二、with_runtime_input_defaults 依赖的问题

现有 infer_inputs.py 里的 with_runtime_input_defaults() 硬编码了五个默认变量（repo_path、readme_path、output_path、retry_count、max_retries）。ProtocolService.dry_run() 在调用 dry_run_contract_check() 之前会注入这些默认值。
这些默认值本质上是"为了让 dry_run 不报 false positive 而打的补丁"，意味着 dry_run 的严格性被降低了。重构后这个问题的解法是：生成的工作流的 frontmatter inputs 声明要准确。Generator 在生成时应该只声明真正需要外部传入的变量，而不是把所有步骤 input 都列入 frontmatter。infer_minimal_inputs() 会优先使用 frontmatter 声明，只有没有声明时才做推断。
with_runtime_input_defaults 保留但缩减：长期来看，这五个默认值应该从 settings.py 读取，而不是硬编码在代码里。重构时把这五个值迁移到 settings.py 的 DEFAULT_WORKFLOW_INPUTS: dict[str, Any]，with_runtime_input_defaults 从 settings 读取，不再硬编码。

## 三、DryRun 的变量可达性分析精度

现有实现是线性的：按步骤顺序依次模拟，前一步的 outputs 加入 available_variables 后供后续步骤使用。这对于没有条件分支的线性流是准确的。
对于有 condition 字段的步骤，现有实现不考虑条件，假设所有步骤都会执行。这会产生 false negative（某步骤实际上可能被跳过，但 dry_run 认为它会产生输出）。
保持现有行为，不在重构中改变 dry_run 的条件分支分析能力。这是一个已知的局限性，加注释说明，未来可以扩展。原因：引入条件分析会使 dry_run 变得复杂，而且条件求值本身依赖运行时 context，静态分析很难做准确。

## 四、DryRunResult、DryRunStepTrace、DryRunContractReport 数据结构

三个 Pydantic 类保持不变，结构是合理的。DryRunResult.status 的 "skipped" 值（在没有 available_context 且没有 enforce_dry_run 时）保留。