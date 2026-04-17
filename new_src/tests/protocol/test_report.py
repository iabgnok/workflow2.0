"""单元测试：report.py 错误回流格式（任务 5.3）"""

import pytest

from agent.engine.protocol.report import ProtocolIssue, ProtocolReport


class TestToDefectDict:
    def test_converts_error_to_defect_format(self):
        issue = ProtocolIssue(
            code="WF_UNKNOWN_ACTIONS",
            message="Unknown action: fake_skill",
            level="error",
            location="step:3",
            suggestion="Use registered skill",
        )
        result = issue.to_defect_dict()
        assert result == {
            "location": "step:3",
            "type": "PROTOCOL_ERROR",
            "reason": "Unknown action: fake_skill",
            "suggestion": "Use registered skill",
        }

    def test_converts_warning_to_defect_format(self):
        issue = ProtocolIssue(
            code="SECURITY_SCAN_CONFIRM_MISSING",
            message="Missing CONFIRM marker",
            level="warning",
            location="workflow:security",
            suggestion="Add [CONFIRM]",
        )
        result = issue.to_defect_dict()
        assert result["type"] == "PROTOCOL_ERROR"
        assert result["location"] == "workflow:security"

    def test_none_location_becomes_empty_string(self):
        issue = ProtocolIssue(code="WF_EMPTY_STEPS", message="No steps", level="error")
        result = issue.to_defect_dict()
        assert result["location"] == ""

    def test_none_suggestion_becomes_empty_string(self):
        issue = ProtocolIssue(code="WF_EMPTY_STEPS", message="No steps", level="error")
        result = issue.to_defect_dict()
        assert result["suggestion"] == ""


class TestErrorsAsDefects:
    def test_only_errors_included(self):
        report = ProtocolReport()
        report.add_error(code="ERR1", message="Error one", location="step:1")
        report.add_error(code="ERR2", message="Error two", location="step:2")
        report.add_warning(code="WARN1", message="Warning one")
        defects = report.errors_as_defects()
        assert len(defects) == 2

    def test_empty_report_returns_empty_list(self):
        report = ProtocolReport()
        assert report.errors_as_defects() == []

    def test_only_warnings_returns_empty_list(self):
        report = ProtocolReport()
        report.add_warning(code="WARN1", message="Just a warning")
        assert report.errors_as_defects() == []

    def test_defect_format_correctness(self):
        report = ProtocolReport()
        report.add_error(
            code="WF_UNKNOWN_ACTIONS",
            message="Unknown action: fake_skill",
            location="step:3",
            suggestion="Use registered skill",
        )
        defects = report.errors_as_defects()
        assert defects[0]["type"] == "PROTOCOL_ERROR"
        assert defects[0]["reason"] == "Unknown action: fake_skill"
        assert defects[0]["location"] == "step:3"

    def test_2_errors_1_warning_returns_2_defects(self):
        report = ProtocolReport()
        report.add_error(code="E1", message="Error 1")
        report.add_error(code="E2", message="Error 2")
        report.add_warning(code="W1", message="Warning 1")
        defects = report.errors_as_defects()
        assert len(defects) == 2
