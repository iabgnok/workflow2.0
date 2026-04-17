"""集成测试：service.py validate_workflow_model（任务 6.2）"""

import pytest

from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.service import ProtocolService


def _make_valid_model(registered_skills: list[str] | None = None) -> WorkflowModel:
    return WorkflowModel.model_validate({
        "metadata": {
            "name": "ValidWorkflow",
            "inputs": ["requirement"],
        },
        "steps": [
            {
                "id": 1,
                "name": "Read",
                "action": "file_reader",
                "inputs": {"requirement": "requirement"},
                "outputs": {"file_content": "file_content"},
                "content": "Read file content.",
            },
            {
                "id": 2,
                "name": "Process",
                "action": "llm_prompt_call",
                "inputs": {"content": "file_content"},
                "outputs": {"result": "result"},
                "content": "Process with LLM.",
            },
        ],
    })


class TestValidateWorkflowModel:
    def setup_method(self):
        self.service = ProtocolService()

    def test_valid_model_passes_all_checks(self):
        model = _make_valid_model()
        result = self.service.validate_workflow_model(
            model,
            registered_skills=["file_reader", "llm_prompt_call"],
            available_context={"requirement": "do something"},
        )
        assert result["valid"] is True
        assert result["summary"] == "ok"

    def test_invalid_action_detected_by_gatekeeper(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "BadAction"},
            "steps": [{
                "id": 1,
                "name": "Step",
                "action": "nonexistent_skill",
                "inputs": {},
                "outputs": {"x": "x"},
                "content": "",
            }],
        })
        result = self.service.validate_workflow_model(
            model,
            registered_skills=["file_reader"],
        )
        assert result["valid"] is False
        assert "nonexistent_skill" in result["summary"]

    def test_result_contains_all_sections(self):
        model = _make_valid_model()
        result = self.service.validate_workflow_model(model)
        assert "valid" in result
        assert "summary" in result
        assert "protocol_report" in result
        assert "dry_run" in result

    def test_dry_run_section_has_expected_keys(self):
        model = _make_valid_model()
        result = self.service.validate_workflow_model(
            model,
            available_context={"requirement": "test"},
        )
        dry = result["dry_run"]
        assert "status" in dry
        assert "required_inputs" in dry
        assert "missing_inputs" in dry
        assert "contract_report" in dry

    def test_security_violation_fails_validation(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "DangerousWorkflow"},
            "steps": [{
                "id": 1,
                "name": "Dangerous",
                "action": "shell",
                "inputs": {},
                "outputs": {"status": "status"},
                "content": "rm -rf /important/data",
            }],
        })
        result = self.service.validate_workflow_model(model)
        assert result["valid"] is False

    def test_error_report_provides_defects(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "ErrWorkflow"},
            "steps": [{
                "id": 1,
                "name": "Step",
                "action": "bad_skill",
                "inputs": {},
                "outputs": {"x": "x"},
                "content": "",
            }],
        })
        result = self.service.validate_workflow_model(
            model,
            registered_skills=["good_skill"],
        )
        # 通过 report 获取 defects 列表
        from agent.engine.protocol.report import ProtocolReport
        report_data = result["protocol_report"]
        issues = report_data.get("issues", [])
        error_issues = [i for i in issues if i["level"] == "error"]
        assert len(error_issues) > 0
