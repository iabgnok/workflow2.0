from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_mapping(value: Any) -> dict[str, str]:
    if value is None:
        return {}

    if isinstance(value, dict):
        result: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            if not key:
                continue
            if raw_value is None:
                result[key] = key
                continue
            val = str(raw_value).strip()
            result[key] = val if val else key
        return result

    if isinstance(value, list):
        result: dict[str, str] = {}
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            if ":" in text:
                left, right = text.split(":", 1)
                key = left.strip()
                val = right.strip()
                if key:
                    result[key] = val if val else key
            else:
                result[text] = text
        return result

    text = str(value).strip()
    if not text:
        return {}
    if ":" in text:
        left, right = text.split(":", 1)
        key = left.strip()
        val = right.strip()
        if key:
            return {key: val if val else key}
        return {}
    return {text: text}


def _normalize_io_list_or_map(value: Any) -> list[str] | dict[str, str]:
    if value is None:
        return []
    if isinstance(value, dict):
        out: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            if not key:
                continue
            val = str(raw_value).strip() if raw_value is not None else key
            out[key] = val if val else key
        return out
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null"}:
        return None
    return text


class WorkflowMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = "UNKNOWN"
    description: Optional[str] = None
    version: Optional[str] = None
    inputs: list[str] | dict[str, str] = Field(default_factory=list)
    outputs: list[str] | dict[str, str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str:
        text = str(value).strip() if value is not None else ""
        return text or "UNKNOWN"

    @field_validator("description", "version", mode="before")
    @classmethod
    def _normalize_optional_metadata_text(cls, value: Any) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("inputs", "outputs", mode="before")
    @classmethod
    def _normalize_ios(cls, value: Any) -> list[str] | dict[str, str]:
        return _normalize_io_list_or_map(value)


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str = ""
    content: str = ""
    action: str
    require_confirm: bool = False
    workflow: Optional[str] = None
    condition: Optional[str] = None
    on_reject: Optional[int] = None
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)

    @field_validator("inputs", "outputs", mode="before")
    @classmethod
    def _normalize_mappings(cls, value: Any) -> dict[str, str]:
        return _normalize_mapping(value)

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, value: Any) -> str:
        text = str(value).strip() if value is not None else ""
        return text or "unknown"

    @field_validator("workflow", "condition", mode="before")
    @classmethod
    def _normalize_optional_step_text(cls, value: Any) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("on_reject", mode="before")
    @classmethod
    def _normalize_on_reject(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            reject_to = int(value)
        except (TypeError, ValueError):
            return None
        return reject_to if reject_to > 0 else None


def _render_io_block(label: str, mapping: dict[str, str]) -> str:
    """渲染 Input/Output 块。"""
    if not mapping:
        return ""
    lines = [f"**{label}**:"]
    for target, source in mapping.items():
        if target == source:
            lines.append(f"- {target}")
        else:
            lines.append(f"- {target}: {source}")
    return "\n".join(lines)


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    metadata: WorkflowMetadata = Field(default_factory=WorkflowMetadata)
    steps: list[WorkflowStep] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _ensure_shape(cls, value: Any) -> Any:
        if value is None:
            return {"metadata": {}, "steps": []}
        if isinstance(value, dict):
            data = dict(value)
            data.setdefault("metadata", {})
            data.setdefault("steps", [])
            return data
        return value

    @classmethod
    def from_parsed_data(cls, parsed_data: dict[str, Any]) -> "WorkflowModel":
        return cls.model_validate(parsed_data)

    def to_markdown(self) -> str:
        """将 WorkflowModel 序列化为标准 .step.md 格式文本。

        生成格式与 WorkflowParser 解析格式完全对应，
        保证 parse(to_markdown()) 可还原等价 WorkflowModel（往返一致性）。
        """
        lines: list[str] = []

        # ── frontmatter ──────────────────────────────────────────────────────
        fm: dict[str, Any] = {"name": self.metadata.name}
        if self.metadata.description:
            fm["description"] = self.metadata.description
        if self.metadata.version:
            fm["version"] = self.metadata.version

        if self.metadata.inputs:
            inputs = self.metadata.inputs
            if isinstance(inputs, list):
                fm["inputs"] = inputs
            else:
                fm["inputs"] = [
                    f"{k}: {v}" if k != v else k for k, v in inputs.items()
                ]

        if self.metadata.outputs:
            outputs = self.metadata.outputs
            if isinstance(outputs, list):
                fm["outputs"] = outputs
            else:
                fm["outputs"] = [
                    f"{k}: {v}" if k != v else k for k, v in outputs.items()
                ]

        lines.append("---")
        lines.append(yaml.dump(fm, allow_unicode=True, default_flow_style=False).rstrip())
        lines.append("---")
        lines.append("")

        # ── steps ─────────────────────────────────────────────────────────────
        for step in self.steps:
            step_header = f"## Step {step.id}"
            if step.name:
                step_header += f": {step.name}"
            lines.append(step_header)

            # Action（含 [CONFIRM] 标记）
            action_line = f"**Action**: `{step.action}`"
            if step.require_confirm:
                action_line += " [CONFIRM]"
            lines.append(action_line)

            # 可选字段
            if step.condition:
                lines.append(f"**Condition**: `{step.condition}`")
            if step.workflow:
                lines.append(f"**Workflow**: `{step.workflow}`")
            if step.on_reject is not None:
                lines.append(f"**on_reject**: `{step.on_reject}`")

            # Input / Output
            if step.inputs:
                lines.append(_render_io_block("Input", step.inputs))
            if step.outputs:
                lines.append(_render_io_block("Output", step.outputs))

            lines.append("")

        return "\n".join(lines)
