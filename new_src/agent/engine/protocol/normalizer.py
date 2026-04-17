import re
import warnings
from typing import Any


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null"}:
        return None
    return text


def _coerce_step_id(raw_value: Any, fallback: int) -> int:
    if raw_value in (None, ""):
        return fallback
    try:
        step_id = int(raw_value)
    except (TypeError, ValueError):
        return fallback
    return step_id if step_id > 0 else fallback


def _coerce_on_reject(raw_value: Any) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        reject_to = int(raw_value)
    except (TypeError, ValueError):
        return None
    return reject_to if reject_to > 0 else None


def _extract_legacy_on_reject(metadata: dict[str, Any]) -> tuple[int | None, bool]:
    for key in ("on_reject", "onReject", "on-reject"):
        if key in metadata:
            return _coerce_on_reject(metadata.get(key)), True
    return None, False


def _select_legacy_on_reject_target_index(steps: list[dict[str, Any]]) -> int | None:
    if not steps:
        return None

    evaluator_like_indexes: list[int] = []
    for idx, step in enumerate(steps):
        action = str(step.get("action") or "").strip().lower()
        outputs = step.get("outputs") or {}
        output_keys: set[str] = set()
        if isinstance(outputs, dict):
            output_keys = {str(k).strip().lower() for k in outputs.keys()}
        if "evaluator_report" in output_keys or "evaluator" in action:
            evaluator_like_indexes.append(idx)

    if evaluator_like_indexes:
        return evaluator_like_indexes[-1]
    return len(steps) - 1


def _normalize_mapping(value: Any) -> dict[str, str]:
    if value is None:
        return {}
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
        out: dict[str, str] = {}
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            if ":" in text:
                left, right = text.split(":", 1)
                key = left.strip()
                val = right.strip()
                if key:
                    out[key] = val if val else key
            else:
                out[text] = text
        return out
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


def normalize_parsed_data(parsed_data: dict[str, Any]) -> dict[str, Any]:
    raw = parsed_data or {}
    metadata = dict(raw.get("metadata") or {})
    for key in ("name", "description", "version"):
        if key in metadata and metadata[key] is not None:
            metadata[key] = str(metadata[key]).strip()
    if not str(metadata.get("name") or "").strip():
        metadata["name"] = "UNKNOWN"
    legacy_on_reject, legacy_on_reject_used = _extract_legacy_on_reject(metadata)
    metadata["on_reject"] = legacy_on_reject
    metadata["_legacy_on_reject_used"] = legacy_on_reject_used
    steps = raw.get("steps") or []

    normalized_steps: list[dict[str, Any]] = []
    for idx, step in enumerate(steps, start=1):
        item = dict(step or {})
        item["id"] = _coerce_step_id(item.get("id"), idx)
        item["name"] = str(item.get("name") or "").strip()
        item["content"] = str(item.get("content") or "")
        action = str(item.get("action") or "").strip()
        item["action"] = action or "unknown"

        item["workflow"] = _normalize_optional_text(item.get("workflow"))

        item["condition"] = _normalize_optional_text(item.get("condition"))

        item["on_reject"] = _coerce_on_reject(item.get("on_reject"))

        item["inputs"] = _normalize_mapping(item.get("inputs"))
        item["outputs"] = _normalize_mapping(item.get("outputs"))
        normalized_steps.append(item)

    # Legacy DSL compatibility: allow frontmatter-level on_reject as default
    # by projecting it to a concrete step when no step-level on_reject exists.
    has_step_level_on_reject = any(step.get("on_reject") is not None for step in normalized_steps)
    if legacy_on_reject is not None and not has_step_level_on_reject:
        target_index = _select_legacy_on_reject_target_index(normalized_steps)
        if target_index is not None:
            normalized_steps[target_index]["on_reject"] = legacy_on_reject

    return {
        "metadata": metadata,
        "steps": normalized_steps,
    }


def sanitize_artifact_for_engine(artifact: str) -> str:
    """
    .. deprecated::
        此函数已标记为 Deprecated。
        当 Generator 结构化路径（WorkflowModel 直接持久化）完全落地后将删除。
        请使用 WorkflowModel.to_markdown() 代替。
    """
    warnings.warn(
        "sanitize_artifact_for_engine() is deprecated. "
        "Use WorkflowModel.to_markdown() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _sanitize_artifact_for_engine_impl(artifact)


def _sanitize_artifact_for_engine_impl(artifact: str) -> str:
    """内部实现，供 normalize_generated_artifact 调用（不触发 DeprecationWarning）。"""
    text = (artifact or "").strip()
    if not text:
        return text

    # 归一化 {{inputs.x}} 到 x
    text = re.sub(r'\{\{\s*inputs\.([a-zA-Z0-9_]+)\s*\}\}', r'\1', text)

    # 将常见的自映射写法 `- x: {{x}}` 归一化为 `- x`
    text = re.sub(
        r'(?m)^(\s*-\s*)([a-zA-Z0-9_]+)\s*:\s*\{\{\s*\2\s*\}\}\s*$',
        r'\1\2',
        text,
    )

    cleaned_lines = []
    for line in text.splitlines():
        # 清理明显不可落地的 steps.* 引用
        if re.search(r'^\s*-\s*[a-zA-Z0-9_]+\s*:\s*\{\{\s*steps\.', line):
            continue
        line = re.sub(
            r'^(\s*-\s*)([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_]+)\s*$',
            lambda m: f"{m.group(1)}{m.group(2)}" if m.group(2) == m.group(3) else line,
            line,
        )
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip() + "\n"


def normalize_generated_artifact(content: str) -> str:
    """
    .. deprecated::
        此函数已标记为 Deprecated。
        当 Generator 结构化路径（WorkflowModel 直接持久化）完全落地后将删除。
        请使用 WorkflowModel.to_markdown() 代替。
    """
    warnings.warn(
        "normalize_generated_artifact() is deprecated. "
        "Use WorkflowModel.to_markdown() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    text = (content or "").strip()
    if not text:
        return text

    text = text.replace("**Inputs**:", "**Input**:")
    text = text.replace("**Outputs**:", "**Output**:")
    text = re.sub(r"^---\s*name:", "---\nname:", text, flags=re.IGNORECASE)
    text = text.replace("---## Step", "---\n\n## Step")
    text = re.sub(
        r"(?m)^(\s*-\s*)([a-zA-Z0-9_]+)\s*:\s*\{\{\s*\2\s*\}\}\s*$",
        r"\1\2",
        text,
    )
    text = re.sub(r"\s*^(## Step\s+\d+.*)", r"\n\n\1", text, flags=re.MULTILINE)
    text = re.sub(r"\s*(\*\*Action\*\*:\s*)", r"\n\1", text)
    text = re.sub(r"\s*(\*\*Condition\*\*:\s*)", r"\n\1", text)
    text = re.sub(r"\s*(\*\*on_reject\*\*:\s*)", r"\n\1", text)
    text = re.sub(r"\s*(\*\*Input\*\*:\s*)", r"\n\1", text)
    text = re.sub(r"\s*(\*\*Output\*\*:\s*)", r"\n\1", text)
    text = re.sub(r"\*\*Input\*\*:\s*-\s*", "**Input**:\n- ", text)
    text = re.sub(r"\*\*Output\*\*:\s*-\s*", "**Output**:\n- ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _sanitize_artifact_for_engine_impl(text)
