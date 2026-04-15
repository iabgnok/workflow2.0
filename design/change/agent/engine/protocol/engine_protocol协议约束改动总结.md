# engine/protocol协议约束改动总结

新增文件：protocol/utils.py（消灭重复工具函数）
主要改动：
    1. gatekeeper.py：删重复函数，import utils，确立 action 检查唯一性，新增错误回流能力
    2. security_scan.py：删 _scan_action_whitelist，新增 scan_workflow_model
    3. models.py：新增 to_markdown()、from_structured_artifact()（[待定]）、RunResult（[待定]）
    4. report.py：新增 to_defect_dict() 和 errors_as_defects()
    5. service.py：新增 validate_workflow_model()
    6. normalizer.py：标注 sanitize_artifact_for_engine / normalize_generated_artifact 为 Deprecated
    7. dry_run.py / runtime_assertions.py：消灭重复函数，import utils

基本不变：errors.py、error_codes.py、infer_inputs.py（小幅调整）