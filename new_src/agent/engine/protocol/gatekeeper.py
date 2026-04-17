from collections.abc import Sequence

from agent.engine.protocol.error_codes import (
    STEP_DUPLICATE_ID,
    STEP_INPUT_TEMPLATE_RESIDUE,
    STEP_INPUT_UNBOUND,
    STEP_INVALID_ACTION,
    STEP_INVALID_IO_HEADER,
    STEP_MISSING_OUTPUT,
    STEP_ON_REJECT_NOT_BACKWARD,
    STEP_ON_REJECT_TARGET_MISSING,
    STEP_OUTPUT_TEMPLATE_RESIDUE,
    WF_EMPTY_STEPS,
    WF_UNKNOWN_ACTIONS,
)
from agent.engine.protocol.infer_inputs import infer_minimal_inputs
from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.report import ProtocolReport
from agent.engine.protocol.utils import extract_metadata_inputs, is_optional_var, normalize_var_name


def validate_workflow(workflow: WorkflowModel, registered_skills: Sequence[str] | None = None) -> ProtocolReport:
    report = ProtocolReport()

    if not workflow.steps:
        report.add_error(
            code=WF_EMPTY_STEPS,
            message="Workflow does not contain executable steps.",
            suggestion="Add at least one step with Action/Input/Output.",
        )
        return report

    seen_ids: set[int] = set()
    all_step_ids = {step.id for step in workflow.steps}
    available_vars = extract_metadata_inputs(workflow)
    # 在迁移期允许"外部输入未显式写入 metadata.inputs"场景，
    # 用最小输入推断结果补齐首步可用变量，避免误报 unbound。
    available_vars.update(infer_minimal_inputs(workflow))

    registered = set(registered_skills) if registered_skills else None

    for step in workflow.steps:
        location = f"step:{step.id}"
        content = str(step.content or "")

        # 复数标题会导致协议漂移，统一在协议层拦截。
        if "**Inputs**:" in content or "**Outputs**:" in content:
            report.add_error(
                code=STEP_INVALID_IO_HEADER,
                message="生成工作流使用了非法的 Input/Output 标题（应为单数 Input/Output）",
                location=location,
                suggestion="将 **Inputs**/**Outputs** 改为 **Input**/**Output**。",
            )

        if step.id in seen_ids:
            report.add_error(
                code=STEP_DUPLICATE_ID,
                message=f"Duplicate step id detected: {step.id}",
                location=location,
            )
        seen_ids.add(step.id)

        if step.on_reject is not None:
            target_id = step.on_reject
            if target_id not in all_step_ids:
                report.add_error(
                    code=STEP_ON_REJECT_TARGET_MISSING,
                    message=f"on_reject points to a non-existent step id: {target_id}",
                    location=location,
                    suggestion="Set on_reject to an existing step id.",
                )
            elif target_id >= step.id:
                report.add_error(
                    code=STEP_ON_REJECT_NOT_BACKWARD,
                    message=f"on_reject must point to an earlier step id, got: {target_id}",
                    location=location,
                    suggestion="Use a step id smaller than the current step for retry loop.",
                )

        if not step.action or step.action == "unknown":
            report.add_error(
                code=STEP_INVALID_ACTION,
                message="Step action is missing or unknown.",
                location=location,
                suggestion="Ensure **Action** is declared and maps to a known skill.",
            )

        # action 白名单检查：逐步报错，location 精确到 step:N
        if registered and step.action and step.action != "unknown":
            if step.action not in registered:
                report.add_error(
                    code=WF_UNKNOWN_ACTIONS,
                    message=f"Step uses unregistered skill: {step.action}",
                    location=location,
                    suggestion="Restrict actions to registered skills.",
                )

        if not step.outputs:
            report.add_error(
                code=STEP_MISSING_OUTPUT,
                message="Step has no output declaration.",
                location=location,
                suggestion="Declare at least one output variable.",
            )

        for source in step.inputs.values():
            src = str(source).strip()
            if "{{" in src and "}}" in src:
                report.add_error(
                    code=STEP_INPUT_TEMPLATE_RESIDUE,
                    message=f"Input mapping contains unresolved template: {src}",
                    location=location,
                    suggestion="Normalize templates before registration.",
                )

            clean = normalize_var_name(src)
            if clean and clean.lower() != "none" and not is_optional_var(src) and clean not in available_vars:
                report.add_error(
                    code=STEP_INPUT_UNBOUND,
                    message=f"Input variable is not reachable at this step: {clean}",
                    location=location,
                )

        for target in step.outputs.keys():
            clean_target = normalize_var_name(str(target))
            if "{{" in str(target) and "}}" in str(target):
                report.add_error(
                    code=STEP_OUTPUT_TEMPLATE_RESIDUE,
                    message=f"Output variable contains template syntax: {target}",
                    location=location,
                )
            if clean_target and clean_target.lower() != "none":
                available_vars.add(clean_target)

    if report.has_errors():
        report.passed = False
    return report
