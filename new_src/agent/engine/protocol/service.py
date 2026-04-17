from typing import Any

from pydantic import ValidationError

from agent.engine.protocol.dry_run import DryRunResult, dry_run_contract_check
from agent.engine.protocol.error_codes import (
    DSL_LEGACY_ON_REJECT_DEPRECATED,
    PROTOCOL_ISSUE_CODE_CATALOG_VERSION,
    WF_PARSE_FAILED,
    all_protocol_issue_codes,
    protocol_issue_code_catalog,
)
from agent.engine.protocol.errors import ProtocolDryRunError, ProtocolGatekeeperError, ProtocolSchemaError
from agent.engine.protocol.gatekeeper import validate_workflow
from agent.engine.protocol.infer_inputs import infer_minimal_inputs, with_runtime_input_defaults
from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.normalizer import normalize_parsed_data
from agent.engine.protocol.report import ProtocolReport
from agent.engine.protocol.runtime_assertions import validate_step_inputs, validate_step_outputs
from agent.engine.protocol.security_scan import scan_artifact_security, scan_workflow_model


class ProtocolService:
    def __init__(self, parser_cls=None):
        self._parser_cls = parser_cls

    def parse_workflow_file(self, filepath: str) -> tuple[WorkflowModel, dict[str, Any]]:
        if self._parser_cls is None:
            # 延迟导入，避免协议层直接依赖引擎层 Parser
            from agent.engine.parser import WorkflowParser  # type: ignore[import-not-found]
            parser_cls = WorkflowParser
        else:
            parser_cls = self._parser_cls
        parser = parser_cls(filepath)
        parsed = parser.parse()
        return self.parse_parsed_data(parsed)

    def parse_parsed_data(self, parsed_data: dict[str, Any]) -> tuple[WorkflowModel, dict[str, Any]]:
        normalized = normalize_parsed_data(parsed_data)
        try:
            workflow = WorkflowModel.from_parsed_data(normalized)
        except ValidationError as exc:
            raise ProtocolSchemaError(f"Schema validation failed: {exc}") from exc
        return workflow, normalized

    def validate(
        self,
        workflow: WorkflowModel,
        registered_skills: list[str] | None = None,
        raise_on_error: bool = False,
    ) -> ProtocolReport:
        report = validate_workflow(workflow, registered_skills)

        metadata_extra = workflow.metadata.model_extra or {}
        if metadata_extra.get("_legacy_on_reject_used"):
            report.add_warning(
                code=DSL_LEGACY_ON_REJECT_DEPRECATED,
                message="Detected legacy frontmatter on_reject syntax; use step-level **on_reject** instead.",
                location="workflow:metadata",
                suggestion="Move on_reject from frontmatter to the evaluator step.",
            )

        if raise_on_error and report.has_errors():
            raise ProtocolGatekeeperError(report.summary())
        return report

    def dry_run(
        self,
        workflow: WorkflowModel,
        available_context: dict[str, Any] | None = None,
        raise_on_error: bool = False,
    ) -> DryRunResult:
        result = dry_run_contract_check(workflow, with_runtime_input_defaults(available_context))
        if raise_on_error and result.status == "failed":
            raise ProtocolDryRunError(result.report.summary())
        return result

    def infer_required_inputs(self, workflow: WorkflowModel) -> list[str]:
        return infer_minimal_inputs(workflow)

    def validate_workflow_model(
        self,
        model: WorkflowModel,
        registered_skills: list[str] | None = None,
        available_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """对 WorkflowModel 对象执行三检合一：安全扫描 + Gatekeeper + Dry-run。

        不依赖文件路径，直接对内存中的 WorkflowModel 执行校验。
        适用于 Generator 结构化路径（跳过 Markdown 渲染）。

        Returns:
            dict with keys: valid, summary, protocol_report, dry_run
        """
        protocol_report = ProtocolReport()

        # 1. 安全扫描（基于 WorkflowModel 对象）
        security_result = scan_workflow_model(model)
        protocol_report.merge(security_result.to_protocol_report())

        # 2. Gatekeeper 校验
        gatekeeper_report = self.validate(
            model,
            registered_skills=registered_skills,
            raise_on_error=False,
        )
        protocol_report.merge(gatekeeper_report)

        # 3. Dry-run
        dry_run_result = self.dry_run(
            model,
            available_context=available_context,
            raise_on_error=False,
        )
        protocol_report.merge(dry_run_result.report)

        dry_run_payload = {
            "status": dry_run_result.status,
            "required_inputs": list(dry_run_result.required_inputs),
            "missing_inputs": list(dry_run_result.missing_inputs),
            "contract_report": dry_run_result.contract_report.model_dump(),
        }

        return {
            "valid": not protocol_report.has_errors(),
            "summary": protocol_report.summary(),
            "protocol_report": protocol_report.to_audit_dict(),
            "dry_run": dry_run_payload,
        }

    def pre_register_check(
        self,
        workflow: WorkflowModel,
        registered_skills: list[str] | None = None,
        available_context: dict[str, Any] | None = None,
        raise_on_error: bool = False,
    ) -> tuple[ProtocolReport, DryRunResult]:
        gatekeeper_report = self.validate(
            workflow,
            registered_skills=registered_skills,
            raise_on_error=raise_on_error,
        )
        dry_run_result = self.dry_run(
            workflow,
            available_context=available_context,
            raise_on_error=raise_on_error,
        )
        return gatekeeper_report, dry_run_result

    def build_failure_result(
        self,
        code: str,
        message: str,
        location: str | None = None,
    ) -> dict[str, Any]:
        report = ProtocolReport()
        report.add_error(code=code, message=message, location=location)
        return {
            "valid": False,
            "summary": report.summary(),
            "protocol_report": report.to_audit_dict(),
            "dry_run": {
                "status": "skipped",
                "required_inputs": [],
                "missing_inputs": [],
                "contract_report": {
                    "all_steps_executed": False,
                    "step_io_assertions_passed": False,
                    "no_undefined_variables": False,
                    "no_suppressed_errors": True,
                    "unresolved_variables": [],
                    "traces": [],
                },
            },
        }

    def evaluate_workflow_file(
        self,
        filepath: str,
        registered_skills: list[str] | None = None,
        available_context: dict[str, Any] | None = None,
        enforce_dry_run: bool = False,
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        protocol_report = ProtocolReport()
        dry_run_payload = {
            "status": "skipped",
            "required_inputs": [],
            "missing_inputs": [],
            "contract_report": {
                "all_steps_executed": False,
                "step_io_assertions_passed": False,
                "no_undefined_variables": False,
                "no_suppressed_errors": True,
                "unresolved_variables": [],
                "traces": [],
            },
        }

        try:
            workflow, _ = self.parse_workflow_file(filepath)
        except Exception as exc:
            result = self.build_failure_result(
                code=WF_PARSE_FAILED,
                message=str(exc),
                location="workflow:parse",
            )
            if raise_on_error:
                raise ValueError(result["summary"])
            return result

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                artifact = f.read()
        except OSError:
            artifact = ""

        security_scan_report = scan_artifact_security(
            artifact,
            registered_skills=registered_skills,
        ).to_protocol_report()
        protocol_report.merge(security_scan_report)

        gatekeeper_report = self.validate(
            workflow,
            registered_skills=registered_skills,
            raise_on_error=False,
        )
        protocol_report.merge(gatekeeper_report)

        if enforce_dry_run:
            dry_run_result = self.dry_run(
                workflow,
                available_context=available_context,
                raise_on_error=False,
            )
            dry_run_payload = {
                "status": dry_run_result.status,
                "required_inputs": list(dry_run_result.required_inputs),
                "missing_inputs": list(dry_run_result.missing_inputs),
                "contract_report": dry_run_result.contract_report.model_dump(),
            }
            protocol_report.merge(dry_run_result.report)

        result = {
            "valid": not protocol_report.has_errors(),
            "summary": protocol_report.summary(),
            "protocol_report": protocol_report.to_audit_dict(),
            "dry_run": dry_run_payload,
        }

        if raise_on_error and not result["valid"]:
            raise ValueError(result["summary"])
        return result

    def validate_runtime_step_inputs(self, step: dict, context: dict) -> None:
        validate_step_inputs(step, context)

    def validate_runtime_step_outputs(self, step: dict, output: dict, context: dict) -> None:
        validate_step_outputs(step, output, context)

    def issue_code_catalog(self) -> dict[str, Any]:
        groups = {
            key: list(value)
            for key, value in protocol_issue_code_catalog().items()
            if key != "version"
        }
        return {
            "version": PROTOCOL_ISSUE_CODE_CATALOG_VERSION,
            "groups": groups,
            "all": list(all_protocol_issue_codes()),
        }
