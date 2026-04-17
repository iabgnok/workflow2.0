"""Runner：步骤循环编排器（五阶段，≤150 行）。

解析 → 恢复 → 准备 → 主循环 → 完成。
"""
from __future__ import annotations

import json, logging, os, uuid
from typing import Any

from agent.engine.condition_evaluator import ConditionEvaluator
from agent.engine.execution_hooks import ExecutionHooks, StepHookResult
from agent.engine.execution_observer import DefaultExecutionObserver, ExecutionObserver
from agent.engine.parser import WorkflowParser
from agent.engine.protocol.service import ProtocolService
from agent.engine.resume_strategy import ResumeStrategy
from agent.engine.step_executor import StepExecutor
from config.settings import settings

logger = logging.getLogger(__name__)
_ESCALATION_LIMIT = 4


class EscalationLimitExceeded(Exception):
    pass


class Runner:
    def __init__(self, filepath: str, *, initial_context=None, db_path=None,
                 skill_registry=None, state_store=None, context_manager=None,
                 context_window_tokens=None, hooks=None, observer=None):
        self.filepath = filepath
        self.context: dict[str, Any] = initial_context or {}

        # 基础设施（兼容 old_src 混用期，延迟导入）
        if state_store is None:
            from agent.infra.state_store import SQLiteStateStore
            state_store = SQLiteStateStore(
                db_path or os.path.join(os.path.dirname(__file__), "workflow_state.db")
            )
        self.state_store = state_store

        if skill_registry is None:
            from agent.infra.skill_registry import SkillRegistry
            skill_registry = SkillRegistry()
            skill_registry.scan(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills")))
        self._skill_registry = skill_registry
        self.context["registered_skills"] = sorted(self._skill_registry.get_all().keys())

        if context_manager is None:
            from agent.infra.context_manager import ContextManager
            context_manager = ContextManager()
        _window = int(context_window_tokens or os.environ.get("MYWORKFLOW_CONTEXT_WINDOW_TOKENS", "120000"))

        from agent.infra.error_policy import execute_with_policy
        self._protocol = ProtocolService()
        self._executor = StepExecutor(skill_registry, self._protocol, WorkflowParser.replace_variables, execute_with_policy)
        self._evaluator = ConditionEvaluator()
        self._resume = ResumeStrategy()
        self._hooks = hooks or ExecutionHooks()
        self._observer = observer or DefaultExecutionObserver(context_manager, _window)

    async def run(self, run_id: str | None = None) -> dict:
        await self.state_store.connect()
        try:
            return await self._run(run_id)
        finally:
            await self.state_store.close()

    async def _run(self, run_id: str | None) -> dict:
        # Phase 1: 解析
        wf_model, parsed = self._protocol.parse_workflow_file(self.filepath)
        steps, wf_name = parsed["steps"], wf_model.metadata.name or "UNKNOWN"

        # Phase 2: 恢复
        current_run_id = run_id or str(uuid.uuid4())
        start = await self._resume.resume(run_id, self.state_store, self.context)

        # Phase 3: 准备
        self.context.setdefault("prev_defects", [])
        self.context.setdefault("escalation_level", 1)
        await self.state_store.save_run_state(current_run_id, wf_name, "running", start, self.context)
        await self._hooks.on_run_start(current_run_id, self.context)
        await self._observer.on_step_start(0, self.context)
        logger.info("🚀 [%s] %d 步。Run ID: %s", wf_name, len(steps), current_run_id)

        # Phase 4: 主循环
        counters: dict[int, int] = {}
        idx = start - 1
        while idx < len(steps):
            step = steps[idx]
            logger.info("▶️  [Step %s] %s | %s", step["id"], step["name"], step["action"])

            skip, reason = self._evaluator.eval(step.get("condition"), self.context)
            if skip:
                logger.info("⏭️  Step %s %s，跳过。", step["id"], reason)
                idx += 1; continue

            hook_result = await self._safe_hook_before(step)
            if hook_result.skip:
                idx += 1; continue

            await self.state_store.save_run_state(current_run_id, wf_name, "running", step["id"], self.context)
            await self._observer.on_step_start(step["id"], self.context)

            try:
                output = await self._executor.execute(step, self.context)
            except Exception as exc:
                await self._fail(current_run_id, wf_name, step, exc)
                await self._observer.flush(current_run_id, self.context, self.state_store)
                raise

            self.context.update(output)
            await self._observer.on_step_end(step["id"], self.context)
            await self._safe_hook_after(step, output)
            await self.state_store.save_step_state(current_run_id, step["id"], "success", output, self.context)

            # on_reject 路由
            raw = output.get("evaluator_report")
            if raw is not None and _parse_report(raw).get("status") == "REJECTED":
                target = step.get("on_reject")
                if target is not None:
                    idx = self._reject(steps, step, target, _parse_report(raw), counters)
                    continue

            idx += 1

        # Phase 5: 完成
        await self._hooks.on_run_end(current_run_id, self.context)
        await self.state_store.save_run_state(current_run_id, wf_name, "completed", len(steps), self.context)
        await self._observer.flush(current_run_id, self.context, self.state_store)
        logger.info("🎉 工作流完成。Run ID: %s", current_run_id)
        final_status = self._derive_final_status(self.context, wf_name)
        return {"run_id": current_run_id, "status": final_status, "context": self.context}

    def _derive_final_status(self, context: dict[str, Any], workflow_name: str) -> str:
        # 内层回放 Runner 保持旧语义，避免污染外层 replay 判定。
        if context.get("__skip_auto_replay__") is True:
            return "success"

        name = str(workflow_name or "").strip().lower()
        is_meta_workflow = "meta main workflow" in name
        if not is_meta_workflow:
            return "success"

        report = _parse_report(context.get("evaluator_report"))
        if not report:
            return "success"

        if report.get("status") != "APPROVED":
            return "rejected"

        try:
            score = int(report.get("score", -1))
        except (TypeError, ValueError):
            score = -1
        min_quality_score = int(getattr(settings, "min_quality_score", 60))
        if score < min_quality_score:
            return "rejected"

        replay = context.get("generated_workflow_replay")
        if not isinstance(replay, dict):
            return "approved_unverified"

        if replay.get("status") == "success":
            return "success"
        return "replay_failed"

    def _reject(self, steps, step, target_id, report, counters):
        latest_defects = self._dedupe_defects(self._normalize_defects(report.get("defects", [])))
        machine_only = bool(latest_defects) and all(
            str(d.get("fix_category") or "") == "machine-fixable" for d in latest_defects
        )

        if machine_only:
            key = f"__machine_fix_attempts_{target_id}"
            machine_attempts = int(self.context.get(key, 0)) + 1
            self.context[key] = machine_attempts
            max_machine_attempts = int(getattr(settings, "structured_validation_max_retries", 1)) + 1
            if machine_attempts <= max_machine_attempts:
                count = counters.get(target_id, 0)
            else:
                counters[target_id] = counters.get(target_id, 0) + 1
                count = counters[target_id]
                self.context[key] = 0
        else:
            counters[target_id] = counters.get(target_id, 0) + 1
            count = counters[target_id]

        logger.warning("🔙 REJECTED → Step %s（第 %d 轮）", target_id, count)
        if count >= _ESCALATION_LIMIT:
            raise EscalationLimitExceeded(
                f"Step {target_id} 连续被打回 {count} 次，请人工干预。最后反馈：{report.get('overall_feedback', '无')}"
            )

        previous_defects = self._dedupe_defects(list(self.context.get("prev_defects") or []))
        self.context.update(
            {
                "escalation_level": max(1, count),
                "prev_defects": latest_defects,
                "prev_defects_summary": {
                    "previous_count": len(previous_defects),
                    "latest_count": len(latest_defects),
                    "latest_types": sorted({str(d.get("type") or "UNKNOWN") for d in latest_defects}),
                    "machine_only": machine_only,
                },
                "chat_history": [],
            }
        )
        self.context.pop("pre_evaluator_defects", None)
        self.context.pop("evaluator_report", None)
        logger.info("🧹 对话历史已清空。")
        target_idx = next((i for i, s in enumerate(steps) if s["id"] == target_id), -1)
        if target_idx == -1:
            raise ValueError(f"on_reject 目标 Step {target_id} 不存在。")
        return target_idx

    @staticmethod
    def _normalize_defects(raw_defects: Any) -> list[dict]:
        if not isinstance(raw_defects, list):
            return []
        normalized: list[dict] = []
        for item in raw_defects:
            if isinstance(item, dict):
                normalized.append(item)
                continue
            text = str(item).strip()
            if text:
                normalized.append(
                    {
                        "location": "workflow:unknown",
                        "type": "LOGIC_ERROR",
                        "reason": text,
                        "suggestion": "请根据缺陷描述修复后重试。",
                    }
                )
        return normalized

    @staticmethod
    def _dedupe_defects(defects: list[dict]) -> list[dict]:
        seen: set[tuple[str, str, str]] = set()
        result: list[dict] = []
        for defect in defects:
            location = str(defect.get("location") or "")
            defect_type = str(defect.get("type") or "")
            reason = str(defect.get("reason") or "")
            key = (location, defect_type, reason)
            if key in seen:
                continue
            seen.add(key)
            result.append(defect)
        return result

    async def _safe_hook_before(self, step) -> StepHookResult:
        try:
            return await self._hooks.on_step_before(step, self.context)
        except Exception as exc:
            logger.error("Hook before 异常（已隔离）: %s", exc)
            return StepHookResult()

    async def _safe_hook_after(self, step, output) -> None:
        try:
            await self._hooks.on_step_after(step, output, self.context)
        except Exception as exc:
            logger.error("Hook after 异常（已隔离）: %s", exc)

    async def _fail(self, run_id, wf_name, step, exc) -> None:
        err = {"error": str(exc)}
        await self.state_store.save_step_state(run_id, step["id"], "failed", err, self.context)
        await self.state_store.save_run_state(run_id, wf_name, f"failed: {exc}", step["id"], self.context)


def _parse_report(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("⚠️ evaluator_report 无法解析，忽略。")
    return {}
