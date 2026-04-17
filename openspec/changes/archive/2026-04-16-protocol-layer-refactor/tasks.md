## 1. 新增 protocol/utils.py

- [x] 1.1 创建 `new_src/agent/engine/protocol/utils.py`，实现 `normalize_var_name(value: str) -> str`
- [x] 1.2 实现 `extract_metadata_inputs(workflow: WorkflowModel) -> set[str]`
- [x] 1.3 实现 `is_optional_var(value: str) -> bool`
- [x] 1.4 编写 utils.py 的单元测试

## 2. models.py 扩展

- [x] 2.1 WorkflowStep 新增 `require_confirm: bool = False` 字段
- [x] 2.2 WorkflowModel 新增 `to_markdown() -> str` 方法（从 generator._render_markdown 迁移逻辑）
- [x] 2.3 为 to_markdown() 编写往返一致性测试

## 3. gatekeeper.py 重构

- [x] 3.1 删除 `_normalize_name` 和 `_extract_metadata_inputs`，改为从 `protocol.utils` import
- [x] 3.2 将 action 白名单检查从全局汇总移到逐步遍历中，location 改为 `step:{step.id}`
- [x] 3.3 验证所有现有 Gatekeeper 测试仍通过

## 4. security_scan.py 重构

- [x] 4.1 删除 `_scan_action_whitelist()` 函数
- [x] 4.2 新增 `scan_workflow_model(model: WorkflowModel) -> SecurityScanResult` 函数
- [x] 4.3 更新 `scan_artifact_security()` 签名，移除或忽略 `registered_skills` 参数
- [x] 4.4 编写 scan_workflow_model 的单元测试

## 5. report.py 扩展

- [x] 5.1 ProtocolIssue 新增 `to_defect_dict() -> dict` 方法
- [x] 5.2 ProtocolReport 新增 `errors_as_defects() -> list[dict]` 方法
- [x] 5.3 编写错误回流格式的单元测试

## 6. service.py 扩展

- [x] 6.1 新增 `validate_workflow_model(model, registered_skills, available_context)` 方法
- [x] 6.2 编写集成测试验证三检合一（security_scan + gatekeeper + dry_run）

## 7. dry_run.py / runtime_assertions.py 清理

- [x] 7.1 dry_run.py：删除重复函数，import from protocol.utils
- [x] 7.2 runtime_assertions.py：删除 `_normalize_var_name`，import from protocol.utils
- [x] 7.3 runtime_assertions.py：统一使用 `is_optional_var()` 判断可选变量

## 8. normalizer.py / infer_inputs.py / error_codes.py 调整

- [x] 8.1 normalizer.py：标注 `sanitize_artifact_for_engine` 和 `normalize_generated_artifact` 为 Deprecated
- [x] 8.2 infer_inputs.py：`with_runtime_input_defaults()` 改为从 `settings.default_workflow_inputs` 读取
- [x] 8.3 error_codes.py：确认现有码值不变，预留 `WF_STRUCTURED_ARTIFACT_INVALID` 码位

## 9. 回归验证

- [x] 9.1 运行协议层全部现有单元测试确认无回归
- [x] 9.2 验证 protocol/ 目录下无文件 import protocol 层外部模块（保持零外部依赖）
