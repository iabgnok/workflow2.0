from agent.engine.protocol.models import WorkflowModel

# 内置的安全运行时默认值，当 settings 模块不可用时作为降级兜底。
# 这些默认值覆盖通用工作流变量，减少干跑（dry-run）对非业务变量的误报。
_BUILTIN_DEFAULTS: dict = {
    "repo_path": ".",
    "readme_path": "README.md",
    "output_path": "output.txt",
    "retry_count": 0,
    "max_retries": 3,
}


def _get_workflow_input_defaults() -> dict:
    """从 settings 读取 default_workflow_inputs，不可用时降级为内置默认值。"""
    try:
        from agent.settings import settings  # type: ignore[import-not-found]
        return dict(getattr(settings, "default_workflow_inputs", None) or _BUILTIN_DEFAULTS)
    except (ImportError, AttributeError):
        return dict(_BUILTIN_DEFAULTS)


def with_runtime_input_defaults(available_context: dict | None) -> dict:
    """注入运行时默认输入变量，减少 dry-run 对通用变量的误报。"""
    context = dict(available_context or {})
    defaults = _get_workflow_input_defaults()
    for key, value in defaults.items():
        context.setdefault(key, value)
    return context


def infer_minimal_inputs(workflow: WorkflowModel) -> list[str]:
    metadata_inputs = workflow.metadata.inputs

    if isinstance(metadata_inputs, dict):
        required = [str(k).strip() for k in metadata_inputs.keys() if str(k).strip()]
    else:
        required = [str(x).strip() for x in metadata_inputs if str(x).strip()]

    if required:
        return sorted(set(required))

    inferred: list[str] = []
    for step in workflow.steps:
        for source in step.inputs.values():
            src = str(source).strip().strip("`").strip()
            if not src or src.lower() == "none":
                continue
            if src.endswith("?"):
                continue
            if src.startswith("{{") and src.endswith("}}"):
                src = src[2:-2].strip()
            inferred.append(src)

    return sorted(set(x for x in inferred if x))
