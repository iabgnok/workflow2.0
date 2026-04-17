"""Meta Workflow 入口（new_src）。

构造 ChampionTracker 并注入 Runner，驱动 Meta Main Workflow 执行。

用法：
    python -m main <workflow_file> [run_id]
    WORKFLOWS_ROOT=/path/to/workflows python -m main meta.step.md
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


async def run_meta_workflow(
    filepath: str,
    initial_context: dict | None = None,
    run_id: str | None = None,
    db_path: str | None = None,
    workflows_root: str | None = None,
    index_path: str | None = None,
) -> dict:
    """构造基础设施、组装 ChampionTracker，运行工作流。"""
    from agent.infra.state_store import SQLiteStateStore
    from agent.infra.workflow_registry import WorkflowRegistry
    from agent.engine.protocol.service import ProtocolService
    from agent.orchestration.champion_tracker import ChampionTracker
    from agent.engine.runner import Runner
    from agent.infra.context_manager import ContextManager

    # 基础设施
    _db_path = db_path or os.path.join(os.path.dirname(__file__), "workflow_state.db")
    _workflows_root = workflows_root or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "agent", "workflows")
    )
    _index_path = index_path or os.path.join(_workflows_root, "registry", "index.json")

    from agent.infra.skill_registry import SkillRegistry

    state_store = SQLiteStateStore(_db_path)
    workflow_registry = WorkflowRegistry(_workflows_root, _index_path)
    protocol_service = ProtocolService()

    skill_registry = SkillRegistry()
    _skills_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent", "skills"))
    skill_registry.scan(_skills_root)

    # 组装 ChampionTracker
    champion_tracker = ChampionTracker(
        state_store=state_store,
        workflow_registry=workflow_registry,
        protocol_service=protocol_service,
        workflows_root=_workflows_root,
        index_path=_index_path,
    )

    # 构造 Runner，注入 ChampionTracker 作为 hooks
    runner = Runner(
        filepath=filepath,
        initial_context=initial_context or {},
        skill_registry=skill_registry,
        state_store=state_store,
        context_manager=ContextManager(),
        hooks=champion_tracker,
    )

    return await runner.run(run_id=run_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m main <workflow_file> [run_id]")
        sys.exit(1)

    wf_file = sys.argv[1]
    _run_id = sys.argv[2] if len(sys.argv) > 2 else None

    result = asyncio.run(run_meta_workflow(filepath=wf_file, run_id=_run_id))
    print(f"\n✅ Run ID: {result['run_id']} | 状态: {result['status']}")
