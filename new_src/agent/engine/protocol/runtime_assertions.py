from agent.engine.protocol.errors import ProtocolRuntimeValidationError
from agent.engine.protocol.utils import is_optional_var, normalize_var_name


def validate_step_inputs(step: dict, context: dict) -> None:
    declared_inputs = step.get("inputs", {}) or {}
    missing = []
    for target_name, source_name in declared_inputs.items():
        raw = (target_name or "").strip()
        if raw.lower() == "none":
            continue
        source_raw = (source_name or "").strip() if isinstance(source_name, str) else ""
        if source_raw.lower() == "none":
            continue
        clean_name = normalize_var_name(source_raw or raw)
        if not clean_name:
            continue
        if not is_optional_var(raw) and clean_name not in context:
            missing.append(clean_name)

    if missing:
        raise ProtocolRuntimeValidationError(
            f"步骤 {step.get('id', '?')} 前置断言失败：以下输入变量在 context 中不存在: {missing}"
        )


def validate_step_outputs(step: dict, output: dict, context: dict) -> None:
    declared_outputs = step.get("outputs", {}) or {}
    missing = []
    for parent_var in declared_outputs.keys():
        raw = (parent_var or "").strip()
        if raw.lower() == "none":
            continue
        clean_name = normalize_var_name(raw)
        if not clean_name:
            continue
        if clean_name not in output and clean_name not in context:
            missing.append(clean_name)

    if missing:
        raise ProtocolRuntimeValidationError(
            f"步骤 {step.get('id', '?')} 后置断言失败：以下输出变量未被技能产生: {missing}"
        )
