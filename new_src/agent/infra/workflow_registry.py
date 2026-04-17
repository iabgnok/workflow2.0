"""工作流注册中心。

管理工作流文件的存储、索引、验证和检索。
新增 register_workflow_model() 方法，支持直接注册内存中的 WorkflowModel 对象，
注册前强制执行 DryRun 契约检查。

注意：本模块依赖 agent.engine.protocol（共享契约层），
      这是 infra 层唯一允许的对 engine 子包的导入。
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

from agent.engine.protocol.error_codes import ENTRY_FILE_MISSING, ENTRY_RESOLVE_FAILED
from agent.engine.protocol.models import WorkflowModel
from agent.engine.protocol.service import ProtocolService
from agent.engine.protocol.normalizer import sanitize_artifact_for_engine

logger = logging.getLogger(__name__)


class WorkflowRegistry:
    """工作流注册中心。

    管理工作流的生命周期：注册、路径解析、验证和清理。
    支持两种注册入口：
    - register_generated_workflow(): 从 Markdown 文本注册。
    - register_workflow_model(): 从内存 WorkflowModel 对象注册（DryRun 前置校验）。
    """

    def __init__(self, workflows_root: str, index_path: str | None = None):
        self.workflows_root = workflows_root
        self.index_path = index_path or os.path.join(workflows_root, "registry", "index.json")
        self.dev_dir = os.path.join(workflows_root, "dev")
        self.protocol_service = ProtocolService()

    def ensure_ready(self) -> None:
        os.makedirs(self.dev_dir, exist_ok=True)
        if not os.path.exists(self.index_path):
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

    # ── 从 Markdown 文本注册 ──────────────────────────────────────────────────

    def register_generated_workflow(
        self,
        artifact: str,
        description: str = "",
        registered_skills=None,
        available_context=None,
    ) -> dict:
        """从 Markdown 工作流文本注册，写入 dev/ 目录并更新索引。"""
        self.ensure_ready()
        sanitized = sanitize_artifact_for_engine(artifact)
        workflow_name = self._extract_name(sanitized) or "generated_workflow"
        workflow_id = self._build_workflow_id(workflow_name)
        workflow_filename = f"{workflow_id}.step.md"
        workflow_path = os.path.join(self.dev_dir, workflow_filename)
        with open(workflow_path, "w", encoding="utf-8") as f:
            f.write(sanitized)
        try:
            validation_result = self._validate_engine_compatibility(
                workflow_path,
                registered_skills or [],
                available_context=available_context,
                enforce_dry_run=True,
                raise_on_error=True,
            )
        except Exception:
            if os.path.exists(workflow_path):
                os.remove(workflow_path)
            raise

        data = self._read_index()
        stored_path = self._build_stored_path(workflow_path)
        data[workflow_id] = {
            "path": stored_path,
            "description": description or workflow_name,
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._write_index(data)
        return {
            "workflow_id": workflow_id,
            "workflow_path": self._to_posix(workflow_path),
            "protocol_report": validation_result.get("protocol_report", {}),
            "dry_run": validation_result.get("dry_run", {"status": "skipped"}),
            "protocol_summary": validation_result.get("summary", "ok"),
        }

    # ── 从 WorkflowModel 对象注册（新增）──────────────────────────────────────

    def register_workflow_model(
        self,
        model: WorkflowModel,
        description: str = "",
        registered_skills: list[str] | None = None,
        available_context: dict | None = None,
    ) -> dict:
        """直接注册内存中的 WorkflowModel 对象。

        注册前执行三检合一（安全扫描 + Gatekeeper + DryRun）。
        若 DryRun 失败，不写入 index.json，返回失败报告。

        Args:
            model:             要注册的 WorkflowModel 对象。
            description:       工作流描述（可选）。
            registered_skills: 已注册技能名称列表，用于 Gatekeeper 验证。
            available_context: 可用上下文变量，用于 DryRun 验证。

        Returns:
            包含 workflow_id、validation 结果的字典。
            若验证失败，字典包含 valid=False 和 failure_report。
        """
        validation_result = self.protocol_service.validate_workflow_model(
            model,
            registered_skills=registered_skills,
            available_context=available_context,
        )

        if not validation_result.get("valid", False):
            logger.warning(
                "❌ WorkflowModel 注册失败（DryRun/Gatekeeper 未通过）: %s",
                validation_result.get("summary"),
            )
            return {
                "valid": False,
                "workflow_id": None,
                "failure_report": validation_result,
            }

        self.ensure_ready()
        workflow_name = model.metadata.name if model.metadata and model.metadata.name else "generated_workflow"
        workflow_id = self._build_workflow_id(workflow_name)

        data = self._read_index()
        data[workflow_id] = {
            "model_registered": True,
            "description": description or workflow_name,
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._write_index(data)

        return {
            "valid": True,
            "workflow_id": workflow_id,
            "protocol_report": validation_result.get("protocol_report", {}),
            "dry_run": validation_result.get("dry_run", {}),
            "protocol_summary": validation_result.get("summary", "ok"),
        }

    # ── 路径解析 ─────────────────────────────────────────────────────────────

    def resolve_path(self, workflow_id: str) -> str:
        data = self._read_index()
        if workflow_id not in data:
            raise KeyError(f"未找到 workflow_id: {workflow_id}")
        path = data[workflow_id].get("path")
        if not path:
            raise KeyError(f"workflow_id={workflow_id} 缺少 path")
        absolute = path if os.path.isabs(path) else os.path.join(os.getcwd(), path)
        return os.path.abspath(absolute)

    # ── 验证 ─────────────────────────────────────────────────────────────────

    def validate_entry(self, workflow_id: str, registered_skills=None) -> tuple[bool, str]:
        report = self.validate_entry_report(workflow_id, registered_skills=registered_skills)
        return report["valid"], report["summary"]

    def validate_entry_report(
        self,
        workflow_id: str,
        registered_skills=None,
        available_context=None,
    ) -> dict:
        try:
            workflow_path = self.resolve_path(workflow_id)
        except Exception as exc:
            from agent.engine.protocol.service import ProtocolService
            result = self.protocol_service.build_failure_result(
                code=ENTRY_RESOLVE_FAILED,
                message=f"路径解析失败: {exc}",
                location=f"workflow:{workflow_id}",
            ) if hasattr(self.protocol_service, "build_failure_result") else {
                "valid": False,
                "summary": f"路径解析失败: {exc}",
            }
            result["workflow_id"] = workflow_id
            result["workflow_path"] = None
            return result
        if not os.path.exists(workflow_path):
            result = {
                "valid": False,
                "summary": f"工作流文件不存在: {workflow_path}",
                "workflow_id": workflow_id,
                "workflow_path": self._to_posix(workflow_path),
            }
            return result
        validation_result = self._validate_engine_compatibility(
            workflow_path,
            registered_skills or [],
            available_context=available_context,
            enforce_dry_run=False,
            raise_on_error=False,
        )
        validation_result["workflow_id"] = workflow_id
        validation_result["workflow_path"] = self._to_posix(workflow_path)
        return validation_result

    def prune_invalid_generated_workflows(self, registered_skills=None) -> list[dict]:
        self.ensure_ready()
        data = self._read_index()
        removed: list[dict] = []
        kept: dict = {}
        for workflow_id, meta in data.items():
            path = str(meta.get("path", ""))
            is_generated = "/dev/" in path.replace("\\", "/") or workflow_id.startswith("generated_")
            if not is_generated:
                kept[workflow_id] = meta
                continue
            validation = self.validate_entry_report(workflow_id, registered_skills or [])
            if validation["valid"]:
                kept[workflow_id] = meta
                continue
            removed.append({
                "workflow_id": workflow_id,
                "reason": validation["summary"],
                "path": path,
                "validation_report": validation,
            })
            absolute = path if os.path.isabs(path) else os.path.join(os.getcwd(), path)
            if os.path.exists(absolute):
                os.remove(absolute)
        if removed:
            self._write_index(kept)
        return removed

    # ── 私有工具方法 ──────────────────────────────────────────────────────────

    def _extract_name(self, artifact: str) -> str:
        m = re.search(r"(?im)^name:\s*[\"']?([A-Za-z0-9_\-\u4e00-\u9fa5 ]+)", artifact or "")
        return m.group(1).strip() if m else ""

    def _build_workflow_id(self, workflow_name: str) -> str:
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", workflow_name.strip().lower()).strip("_")
        if not base:
            base = "generated_workflow"
        return f"{base}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    def _build_stored_path(self, workflow_path: str) -> str:
        try:
            rel = os.path.relpath(workflow_path, os.getcwd())
            return self._to_posix(rel)
        except ValueError:
            return self._to_posix(os.path.abspath(workflow_path))

    def _read_index(self) -> dict:
        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_index(self, data: dict) -> None:
        tmp_path = self.index_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.index_path)

    def _to_posix(self, path: str) -> str:
        return path.replace("\\", "/")

    def _validate_engine_compatibility(
        self,
        workflow_path: str,
        registered_skills,
        available_context=None,
        enforce_dry_run: bool = False,
        raise_on_error: bool = True,
    ) -> dict:
        return self.protocol_service.evaluate_workflow_file(
            filepath=workflow_path,
            registered_skills=list(registered_skills or []),
            available_context=available_context,
            enforce_dry_run=enforce_dry_run,
            raise_on_error=raise_on_error,
        )
