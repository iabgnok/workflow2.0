"""单元测试：ResumeStrategy（任务 4.2）"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.engine.resume_strategy import ResumeStrategy


def _make_store(
    run_state: dict | None = None,
    latest_step: dict | None = None,
):
    store = MagicMock()
    store.load_run_state = AsyncMock(return_value=run_state)
    store.load_latest_step_state = AsyncMock(return_value=latest_step)
    return store


@pytest.fixture
def strategy():
    return ResumeStrategy()


# ── 新运行（run_id=None）────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_run_starts_at_step_1(strategy):
    store = _make_store()
    ctx = {}
    start = await strategy.resume(None, store, ctx)
    assert start == 1
    store.load_run_state.assert_not_called()


# ── 有 run_id 但无历史记录 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_id_no_state_falls_back_to_step_1(strategy):
    store = _make_store(run_state=None)
    ctx = {}
    start = await strategy.resume("missing-run", store, ctx)
    assert start == 1


# ── 有历史记录、无 step 快照 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resume_uses_run_state_step_id(strategy):
    store = _make_store(
        run_state={"current_step_id": 3, "context": {"x": 1}, "meta_context": {}},
        latest_step=None,
    )
    ctx = {}
    start = await strategy.resume("run-1", store, ctx)
    assert start == 3
    assert ctx.get("x") == 1


# ── 有步骤快照时从 step_id+1 开始 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resume_with_latest_step_advances_past_it(strategy):
    store = _make_store(
        run_state={"current_step_id": 2, "context": {}, "meta_context": {}},
        latest_step={
            "step_id": 3,
            "full_context": {"result": "ok"},
            "meta_full_context": {},
        },
    )
    ctx = {}
    start = await strategy.resume("run-2", store, ctx)
    assert start == 4          # max(2, 3+1) = 4
    assert ctx.get("result") == "ok"


# ── context 注水验证 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_context_hydrated_from_run_state(strategy):
    store = _make_store(
        run_state={
            "current_step_id": 1,
            "context": {"foo": "bar"},
            "meta_context": {"__meta": True},
        },
        latest_step=None,
    )
    ctx = {}
    await strategy.resume("run-3", store, ctx)
    assert ctx["foo"] == "bar"
    assert ctx["__meta"] is True
