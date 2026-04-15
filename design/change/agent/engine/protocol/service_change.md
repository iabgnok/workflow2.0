# protocol/service.py 重构实现细节

## 一、ProtocolService 的方法整理

保留的方法：parse_workflow_file()、parse_parsed_data()、validate()、dry_run()、infer_required_inputs()、pre_register_check()、build_failure_result()、validate_runtime_step_inputs()、validate_runtime_step_outputs()。
evaluate_workflow_file() 的命运：这个方法接受文件路径，内部做解析 + security_scan + gatekeeper + dry_run 的完整流程，是 WorkflowRegistry 的主要调用入口。重构后，注册流程的主路径从"接受文件路径"改为"接受 WorkflowModel 对象"（方向一落地后），这个方法的使用场景变成了"验证已持久化文件的有效性"（validate_entry_report 路径）。保留，但不再是主注册路径的入口。
issue_code_catalog()：只是把 error_codes.py 里的 catalog 包一层，保留。

## 二、新增 validate_workflow_model() 方法

接受 WorkflowModel 直接校验（不经过文件路径），是 security_scan + gatekeeper + dry_run 的组合：

scan_workflow_model(model) → SecurityScanResult（调新增的 WorkflowModel 扫描函数）
validate(model, registered_skills) → ProtocolReport（Gatekeeper）
dry_run(model, available_context) → DryRunResult

把三个结果合并，返回统一的校验结果。这是 WorkflowRegistry.register_workflow_model() 的主要调用入口。

## 三、runtime assertions 的暴露方式

现有 validate_runtime_step_inputs 和 validate_runtime_step_outputs 是 ProtocolService 上的方法，但内部只是转发给 runtime_assertions.py 的函数。这个间接层存在的价值：让 Runner/StepExecutor 只 import ProtocolService，不直接 import runtime_assertions，保持依赖路径的统一。保留这个模式，StepExecutor 通过 protocol_service.validate_runtime_step_inputs() 调用，不直接调 runtime_assertions。