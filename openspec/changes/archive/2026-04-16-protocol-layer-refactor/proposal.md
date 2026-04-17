## Why

协议层是 MyWorkflow 的治理中枢，负责所有确定性规则校验。当前存在三个核心问题：
1. **函数重复** — `_normalize_name()` 在 gatekeeper.py 和 dry_run.py 中各有一份完全相同的实现，`_extract_metadata_inputs()` 同样重复，任何修改存在遗漏风险
2. **action 校验分散** — action 合法性检查在 gatekeeper.py、security_scan.py、llm_generator_call.py 三处各自实现，职责不清
3. **缺少结构化路径支持** — 安全扫描只接受 Markdown 文本字符串，无法处理 WorkflowModel 对象；协议错误无法回流给 Generator 修复循环

## What Changes

- **新增 `protocol/utils.py`**：抽取 `normalize_var_name()`、`extract_metadata_inputs()`、`is_optional_var()` 三个共用函数，消灭 gatekeeper/dry_run/runtime_assertions 中的重复
- **gatekeeper.py**：删除内部重复函数，确立为 action 合法性检查的唯一实现点，检查顺序调整为逐步报错（而非最后汇总），保留 IO_HEADER 最后防线检查
- **security_scan.py**：删除 `_scan_action_whitelist()`（action 检查归 gatekeeper），新增 `scan_workflow_model(WorkflowModel)` 重载
- **models.py**：WorkflowStep 新增 `require_confirm: bool` 字段，WorkflowModel 新增 `to_markdown()` 方法。`from_structured_artifact()` 确定放在 `skills/llm/generator.py` 作为 `to_workflow_model()` 方法（避免协议层→技能层的依赖倒置）；`RunResult` 确定放在 `engine/models.py`（引擎层专属类型）
- **report.py**：ProtocolIssue 新增 `to_defect_dict()` 方法，ProtocolReport 新增 `errors_as_defects()` 方法，支持协议错误回流到 Generator
- **service.py**：新增 `validate_workflow_model()` 方法（组合 security_scan + gatekeeper + dry_run 对 WorkflowModel 校验）
- **dry_run.py / runtime_assertions.py**：删除重复函数，统一从 utils import
- **normalizer.py**：标注 `sanitize_artifact_for_engine()` 和 `normalize_generated_artifact()` 为 Deprecated
- **error_codes.py / errors.py / infer_inputs.py**：小幅调整，保持稳定

## Capabilities

### New Capabilities
- `protocol-utils`: 协议层内部共用工具函数的统一模块，消灭跨文件重复
- `protocol-error-flowback`: 协议校验错误格式化为 Generator 可消费的 defect 格式，支持错误回流修复循环
- `workflow-model-validation`: 直接对 WorkflowModel 对象执行安全扫描和协议校验，支持结构化路径

### Modified Capabilities

## Impact

- protocol/ 目录下 12 个文件中有 9 个需要修改
- gatekeeper 成为 action 合法性的唯一权威来源，security_scan 和 generator 不再重复检查
- 所有消费 protocol 层的模块（Runner、WorkflowRegistry、ChampionTracker）可使用新的 validate_workflow_model() 入口
- report.py 的新方法为后续 orchestration/champion_tracker.py 的错误回流提供接口
