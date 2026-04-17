from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent.engine.protocol.error_codes import (
    STEP_INPUT_TEMPLATE_RESIDUE,
    STEP_INVALID_ACTION,
    STEP_INVALID_IO_HEADER,
    STEP_OUTPUT_TEMPLATE_RESIDUE,
    WF_UNKNOWN_ACTIONS,
)


MACHINE_FIXABLE_CODES = {
    STEP_INVALID_ACTION,
    WF_UNKNOWN_ACTIONS,
    STEP_INVALID_IO_HEADER,
    STEP_INPUT_TEMPLATE_RESIDUE,
    STEP_OUTPUT_TEMPLATE_RESIDUE,
}


class ProtocolIssue(BaseModel):
    code: str
    message: str
    level: Literal["error", "warning"] = "error"
    location: Optional[str] = None
    suggestion: Optional[str] = None

    def fix_category(self) -> Literal["machine-fixable", "model-fixable"]:
        return "machine-fixable" if self.code in MACHINE_FIXABLE_CODES else "model-fixable"

    def to_defect_dict(self) -> dict:
        """将协议错误转换为 Generator prev_defects 可消费的格式。

        返回格式：
            {"location": str, "type": "PROTOCOL_ERROR", "reason": str, "suggestion": str}
        """
        return {
            "location": self.location or "",
            "type": "PROTOCOL_ERROR",
            "code": self.code,
            "fix_category": self.fix_category(),
            "reason": self.message,
            "suggestion": self.suggestion or "",
        }


class ProtocolReport(BaseModel):
    passed: bool = True
    issues: list[ProtocolIssue] = Field(default_factory=list)

    def add_error(self, code: str, message: str, location: Optional[str] = None, suggestion: Optional[str] = None) -> None:
        self.issues.append(
            ProtocolIssue(
                code=code,
                message=message,
                level="error",
                location=location,
                suggestion=suggestion,
            )
        )
        self.passed = False

    def add_warning(self, code: str, message: str, location: Optional[str] = None, suggestion: Optional[str] = None) -> None:
        self.issues.append(
            ProtocolIssue(
                code=code,
                message=message,
                level="warning",
                location=location,
                suggestion=suggestion,
            )
        )

    def has_errors(self) -> bool:
        return any(issue.level == "error" for issue in self.issues)

    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == "error")

    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == "warning")

    def merge(self, other: "ProtocolReport") -> None:
        if not other:
            return
        self.issues.extend(other.issues)
        if other.has_errors():
            self.passed = False

    def summary(self) -> str:
        if not self.issues:
            return "ok"
        return "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues)

    def to_audit_dict(self) -> dict:
        return {
            "passed": not self.has_errors(),
            "summary": self.summary(),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "issues": [issue.model_dump() for issue in self.issues],
        }

    def errors_as_defects(self) -> list[dict]:
        """将所有 error 级别的问题转换为 Generator prev_defects 格式列表。

        警告级别（warning）不包含在内。
        """
        return [
            issue.to_defect_dict()
            for issue in self.issues
            if issue.level == "error"
        ]
