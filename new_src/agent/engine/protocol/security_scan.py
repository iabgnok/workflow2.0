import re
from dataclasses import dataclass, field

from agent.engine.protocol.error_codes import SECURITY_SCAN_CONFIRM_MISSING, SECURITY_SCAN_VIOLATION
from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.report import ProtocolReport


DANGER_KEYWORDS = [
    r"\brm\b",
    r"\brmdir\b",
    r"shutil\.rmtree",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"git\s+push",
    r"git\s+reset\s+--hard",
    r"\bsubprocess\b",
    r"os\.system",
    r"\bshutdown\b",
    r"\breboot\b",
]

CONFIRM_KEYWORDS = [
    r"\bfile_writer\b",
    r"\bgit_commit\b",
    r"http\s+POST",
    r"http\s+PUT",
    r"http\s+PATCH",
    r"\bdeploy\b",
    r"\bpublish\b",
    r"\bsend_email\b",
]


@dataclass
class SecurityScanResult:
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.violations) == 0

    def to_protocol_report(self) -> ProtocolReport:
        report = ProtocolReport()
        for issue in self.violations:
            report.add_error(
                code=SECURITY_SCAN_VIOLATION,
                message=issue,
                location="workflow:security",
                suggestion="为危险操作添加 [DANGER] 标记，或移除不安全操作。",
            )
        for issue in self.warnings:
            report.add_warning(
                code=SECURITY_SCAN_CONFIRM_MISSING,
                message=issue,
                location="workflow:security",
                suggestion="为副作用步骤添加 [CONFIRM] 标记。",
            )
        return report


def _scan_keyword_markers(
    artifact: str,
    patterns: list[str],
    marker: str,
    also_markers: list[str] | None = None,
) -> list[str]:
    findings: list[str] = []
    allowed_markers = {marker}
    allowed_markers.update(also_markers or [])
    lines = artifact.split("\n")
    for pattern in patterns:
        if not re.search(pattern, artifact, re.IGNORECASE):
            continue
        for i, line in enumerate(lines):
            if not re.search(pattern, line, re.IGNORECASE):
                continue
            context_block = "\n".join(lines[max(0, i - 2): min(len(lines), i + 3)])
            if not any(m in context_block for m in allowed_markers):
                findings.append(
                    f"命中关键词 '{pattern}' 但未标记 {marker}，位于行 {i + 1}: {line.strip()}"
                )
    return findings


def scan_artifact_security(artifact: str, registered_skills: list[str] | None = None) -> SecurityScanResult:
    """扫描 Markdown 文本格式的工作流构件。

    注意：`registered_skills` 参数已废弃（action 白名单检查已归 gatekeeper），
    保留签名只为向后兼容，传入的值会被忽略。
    """
    text = artifact or ""
    violations: list[str] = []
    warnings: list[str] = []

    violations.extend(_scan_keyword_markers(text, DANGER_KEYWORDS, "[DANGER]"))

    warnings.extend(
        _scan_keyword_markers(
            text,
            CONFIRM_KEYWORDS,
            "[CONFIRM]",
            also_markers=["[DANGER]"],
        )
    )

    return SecurityScanResult(violations=violations, warnings=warnings)


def scan_workflow_model(model: WorkflowModel) -> SecurityScanResult:
    """直接对 WorkflowModel 对象执行安全扫描。

    扫描每个步骤的 content 字段中的 DANGER/CONFIRM 关键词，
    并读取步骤的 require_confirm 字段（已由 Parser 解析的 [CONFIRM] 标记）。

    使用与 scan_artifact_security 相同的关键词列表，
    差异仅在扫描目标（step.content 字段 vs 原始文本）。
    """
    violations: list[str] = []
    warnings: list[str] = []

    for step in model.steps:
        content = step.content or ""
        location_tag = f"[step:{step.id}]"

        # 危险关键词检查
        for pattern in DANGER_KEYWORDS:
            if re.search(pattern, content, re.IGNORECASE):
                if "[DANGER]" not in content:
                    violations.append(
                        f"{location_tag} 命中危险关键词 '{pattern}' 但未标记 [DANGER]"
                    )
                    break

        # 副作用关键词检查（若步骤已设 require_confirm 则跳过）
        if not step.require_confirm:
            for pattern in CONFIRM_KEYWORDS:
                if re.search(pattern, content, re.IGNORECASE):
                    if "[CONFIRM]" not in content and "[DANGER]" not in content:
                        warnings.append(
                            f"{location_tag} 命中副作用关键词 '{pattern}' 但未标记 [CONFIRM]"
                        )
                        break

    return SecurityScanResult(violations=violations, warnings=warnings)
