"""单元测试：DefaultExecutionObserver（任务 5.2）"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.engine.execution_observer import DefaultExecutionObserver, ExecutionObserver


def _make_cm(ratio: float = 0.3, level: int = 1):
    cm = MagicMock()
    cm.context_pressure_ratio.return_value = ratio
    cm.pressure_level.return_value = level
    return cm


def _make_store():
    store = MagicMock()
    store.save_run_meta = AsyncMock()
    return store


# ── 基类默认空实现 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_base_observer_does_not_raise():
    obs = ExecutionObserver()
    await obs.on_step_start(1, {})
    await obs.on_step_end(1, {})
    await obs.flush("r", {}, MagicMock())


# ── 采样计数 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sample_records_per_step():
    cm = _make_cm(ratio=0.2, level=1)
    obs = DefaultExecutionObserver(cm, context_window_tokens=10000)
    ctx = {}
    await obs.on_step_start(1, ctx)
    await obs.on_step_end(1, ctx)
    assert obs._stats is not None
    assert obs._stats["samples"] == 2


@pytest.mark.asyncio
async def test_max_ratio_tracked():
    cm = MagicMock()
    cm.context_pressure_ratio.side_effect = [0.5, 0.9]
    cm.pressure_level.side_effect = [1, 3]
    obs = DefaultExecutionObserver(cm, context_window_tokens=10000)
    ctx = {}
    await obs.on_step_start(1, ctx)
    await obs.on_step_end(1, ctx)
    assert obs._stats["max_ratio"] == pytest.approx(0.9)
    assert obs._stats["max_level"] == 3


# ── 告警计数 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alerts_counted_at_level_2_or_above():
    cm = MagicMock()
    cm.context_pressure_ratio.side_effect = [0.65, 0.85]
    cm.pressure_level.side_effect = [2, 3]
    obs = DefaultExecutionObserver(cm, 10000)
    ctx = {}
    await obs.on_step_start(1, ctx)
    await obs.on_step_end(1, ctx)
    assert obs._stats["alerts"] == 2


# ── flush ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_flush_saves_to_state_store():
    cm = _make_cm(ratio=0.4, level=1)
    obs = DefaultExecutionObserver(cm, 10000)
    store = _make_store()
    ctx = {}

    await obs.on_step_end(1, ctx)
    await obs.flush("run-1", ctx, store)

    store.save_run_meta.assert_awaited_once()
    assert "context_pressure" in ctx


@pytest.mark.asyncio
async def test_flush_no_samples_skips_store():
    obs = DefaultExecutionObserver(_make_cm(), 10000)
    store = _make_store()
    await obs.flush("run-x", {}, store)
    store.save_run_meta.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_no_run_id_skips():
    cm = _make_cm(ratio=0.5, level=2)
    obs = DefaultExecutionObserver(cm, 10000)
    ctx = {}
    await obs.on_step_end(1, ctx)
    store = _make_store()
    await obs.flush("", ctx, store)
    store.save_run_meta.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_error_does_not_propagate():
    cm = _make_cm(ratio=0.5, level=1)
    obs = DefaultExecutionObserver(cm, 10000)
    ctx = {}
    await obs.on_step_end(1, ctx)
    store = MagicMock()
    store.save_run_meta = AsyncMock(side_effect=Exception("db 爆了"))
    # 不应抛出异常
    await obs.flush("run-2", ctx, store)


# ── 采样失败不影响控制流 ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sample_exception_isolated():
    cm = MagicMock()
    cm.context_pressure_ratio.side_effect = RuntimeError("cm 崩了")
    obs = DefaultExecutionObserver(cm, 10000)
    await obs.on_step_end(1, {})   # 不应抛出
    assert obs._stats is None
