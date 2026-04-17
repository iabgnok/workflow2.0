"""单元测试：security_scan.py scan_workflow_model（任务 4.4）"""

import pytest

from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.security_scan import scan_workflow_model, scan_artifact_security


def _make_step(step_id: int, action: str, content: str, require_confirm: bool = False) -> dict:
    return {
        "id": step_id,
        "name": f"Step {step_id}",
        "action": action,
        "require_confirm": require_confirm,
        "inputs": {},
        "outputs": {f"out{step_id}": f"out{step_id}"},
        "content": content,
    }


class TestScanWorkflowModel:
    def test_clean_workflow_passes(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "Clean"},
            "steps": [_make_step(1, "file_reader", "Read a file safely.")],
        })
        result = scan_workflow_model(model)
        assert result.clean
        assert result.violations == []
        assert result.warnings == []

    def test_danger_keyword_without_marker_is_violation(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "Dangerous"},
            "steps": [_make_step(1, "shell_runner", "rm -rf /tmp/data")],
        })
        result = scan_workflow_model(model)
        assert not result.clean
        assert len(result.violations) == 1
        assert "step:1" in result.violations[0]

    def test_confirm_keyword_without_confirm_is_warning(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "SideEffect"},
            "steps": [_make_step(1, "file_writer", "Write output to file_writer.")],
        })
        result = scan_workflow_model(model)
        assert result.clean  # no violations
        assert len(result.warnings) == 1

    def test_require_confirm_flag_suppresses_warning(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "ConfirmedSideEffect"},
            "steps": [_make_step(1, "file_writer", "Write output to file_writer.", require_confirm=True)],
        })
        result = scan_workflow_model(model)
        assert result.clean
        assert result.warnings == []

    def test_multiple_steps_violations_tracked_per_step(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "Multi"},
            "steps": [
                _make_step(1, "shell_runner", "rm -rf /all"),
                _make_step(2, "shell_runner", "Normal step content"),
            ],
        })
        result = scan_workflow_model(model)
        assert not result.clean
        assert len(result.violations) == 1
        assert "step:1" in result.violations[0]

    def test_to_protocol_report_converts_violations(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "ViolationTest"},
            "steps": [_make_step(1, "shell_runner", "subprocess.run(['rm', '-rf', '/'])")]
        })
        result = scan_workflow_model(model)
        report = result.to_protocol_report()
        assert report.has_errors()


class TestScanArtifactSecurity:
    def test_registered_skills_param_ignored(self):
        # registered_skills 参数已废弃，传入应被忽略不影响结果
        artifact = "**Action**: `unknown_skill`\n**Output**:\n- x"
        result_with = scan_artifact_security(artifact, registered_skills=["known_skill"])
        result_without = scan_artifact_security(artifact)
        assert result_with.violations == result_without.violations
        assert result_with.warnings == result_without.warnings
