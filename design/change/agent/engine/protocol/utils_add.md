# protocol/utils.py（新增）

## 一、为什么新增这个文件

审计时已发现最严重的重复：_normalize_name() 函数在 gatekeeper.py 和 dry_run.py 里各写了一份，代码完全相同。_extract_metadata_inputs() 也在两个文件里各写了一份。这种复制是协议层内部纪律松弛的表现，任何一处修改会产生遗漏风险。新增 utils.py 专门承载协议层内部共用的纯工具函数，消灭所有复制。

## 二、迁入内容

1. normalize_var_name(value: str) -> str：
    将 gatekeeper.py 和 dry_run.py 里的 _normalize_name、以及 runtime_assertions.py 里的 _normalize_var_name 三个逻辑相同的函数统一为一个，命名改为 normalize_var_name（去掉前导下划线，因为是 utils 模块的公开函数），供 gatekeeper、dry_run、runtime_assertions 三个文件共同 import。
    逻辑：strip 两端空格 → strip 反引号 → 如果是 {{...}} 模板则提取内部名 → 如果末尾是 ? 则去掉（可选标记）。
2. extract_metadata_inputs(workflow: 
    WorkflowModel) -> set[str]：将 gatekeeper.py 和 dry_run.py 里各自的 _extract_metadata_inputs 合并为一个。
3. is_optional_var(value: str) -> bool：
    将 dry_run.py 里的 _is_optional_source 和 runtime_assertions.py 里隐式的 raw.endswith("?") 判断统一为一个函数。
    
这三个函数以后即使需要修改逻辑（比如支持新的模板语法），只改一个地方。