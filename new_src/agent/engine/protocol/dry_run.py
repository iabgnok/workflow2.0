from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.engine.protocol.error_codes import (
    DRY_RUN_MISSING_INPUTS,
    DRY_RUN_STEP_INPUT_ASSERT_FAILED,
    DRY_RUN_STEP_OUTPUT_ASSERT_FAILED,
    DRY_RUN_STEP_SKIPPED,
    DRY_RUN_UNDEFINED_VARIABLES,
)
from agent.engine.protocol.infer_inputs import infer_minimal_inputs
from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.report import ProtocolReport
from agent.engine.protocol.utils import extract_metadata_inputs, is_optional_var, normalize_var_name


class DryRunStepTrace(BaseModel):
    step_id: int
    action: str
    executed: bool
    missing_inputs: list[str] = Field(default_factory=list)
    declared_outputs: list[str] = Field(default_factory=list)
    produced_outputs: list[str] = Field(default_factory=list)


class DryRunContractReport(BaseModel):
    all_steps_executed: bool = True
    step_io_assertions_passed: bool = True
    no_undefined_variables: bool = True
    no_suppressed_errors: bool = True
    unresolved_variables: list[str] = Field(default_factory=list)
    traces: list[DryRunStepTrace] = Field(default_factory=list)


class DryRunResult(BaseModel):
    status: Literal["passed", "failed", "skipped"] = "skipped"
    required_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    report: ProtocolReport = Field(default_factory=ProtocolReport)
    contract_report: DryRunContractReport = Field(default_factory=DryRunContractReport)


def dry_run_contract_check(workflow: WorkflowModel, available_context: dict[str, Any] | None = None) -> DryRunResult:
    context = available_context or {}
    required_inputs = infer_minimal_inputs(workflow)
    provided_inputs = {str(name).strip() for name in context.keys() if str(name).strip()}
    available_variables = set(provided_inputs)
    available_variables.update(extract_metadata_inputs(workflow))
    missing_inputs = [name for name in required_inputs if name not in provided_inputs]

    report = ProtocolReport()
    traces: list[DryRunStepTrace] = []
    unresolved_variables: set[str] = set()

    if missing_inputs:
        report.add_error(
            code=DRY_RUN_MISSING_INPUTS,
            message=f"Dry run missing required inputs: {missing_inputs}",
            suggestion="Provide inferred minimal inputs before registration.",
        )

    for step in workflow.steps:
        location = f"step:{step.id}"
        step_missing_inputs: list[str] = []
        for source in step.inputs.values():
            raw_source = str(source).strip()
            clean_source = normalize_var_name(raw_source)
            if not clean_source or clean_source.lower() == "none" or is_optional_var(raw_source):
                continue
            if clean_source not in available_variables:
                step_missing_inputs.append(clean_source)

        declared_outputs: list[str] = []
        for output_name in step.outputs.keys():
            clean_output = normalize_var_name(str(output_name))
            if clean_output and clean_output.lower() != "none":
                declared_outputs.append(clean_output)

        if step_missing_inputs:
            unresolved_variables.update(step_missing_inputs)
            report.add_error(
                code=DRY_RUN_STEP_SKIPPED,
                message=f"Step {step.id} skipped due to missing inputs: {sorted(set(step_missing_inputs))}",
                location=location,
                suggestion="Ensure required variables are produced by previous steps or declared in workflow inputs.",
            )
            report.add_error(
                code=DRY_RUN_STEP_INPUT_ASSERT_FAILED,
                message=f"Step {step.id} input assertions failed.",
                location=location,
            )

        if not declared_outputs:
            report.add_error(
                code=DRY_RUN_STEP_OUTPUT_ASSERT_FAILED,
                message=f"Step {step.id} has no declared output assertions.",
                location=location,
                suggestion="Declare at least one output variable for each executable step.",
            )

        executed = len(step_missing_inputs) == 0
        produced_outputs = declared_outputs if executed else []
        if executed:
            available_variables.update(produced_outputs)

        traces.append(
            DryRunStepTrace(
                step_id=step.id,
                action=step.action,
                executed=executed,
                missing_inputs=sorted(set(step_missing_inputs)),
                declared_outputs=declared_outputs,
                produced_outputs=produced_outputs,
            )
        )

    if unresolved_variables:
        unresolved_sorted = sorted(unresolved_variables)
        report.add_error(
            code=DRY_RUN_UNDEFINED_VARIABLES,
            message=f"Dry run detected unresolved variables: {unresolved_sorted}",
            suggestion="Fix variable mapping or add missing upstream outputs.",
        )
    else:
        unresolved_sorted = []

    all_steps_executed = all(trace.executed for trace in traces) if traces else True
    step_io_assertions_passed = all(
        (trace.executed and len(trace.declared_outputs) > 0)
        for trace in traces
    ) if traces else True
    no_undefined_variables = len(unresolved_sorted) == 0
    no_suppressed_errors = not report.has_errors()

    contract_report = DryRunContractReport(
        all_steps_executed=all_steps_executed,
        step_io_assertions_passed=step_io_assertions_passed,
        no_undefined_variables=no_undefined_variables,
        no_suppressed_errors=no_suppressed_errors,
        unresolved_variables=unresolved_sorted,
        traces=traces,
    )

    status: Literal["passed", "failed", "skipped"] = "failed" if report.has_errors() else "passed"

    return DryRunResult(
        status=status,
        required_inputs=required_inputs,
        missing_inputs=missing_inputs,
        report=report,
        contract_report=contract_report,
    )
