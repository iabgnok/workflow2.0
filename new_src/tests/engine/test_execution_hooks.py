"""单元测试：ExecutionHooks 基类与 StepHookResult（任务 1.2）"""
import pytest
from agent.engine.execution_hooks import ExecutionHooks, StepHookResult


# ── StepHookResult ────────────────────────────────────────────────────────────

def test_step_hook_result_default_no_skip():
    result = StepHookResult()
    assert result.skip is False


def test_step_hook_result_explicit_skip():
    result = StepHookResult(skip=True)
    assert result.skip is True


# ── ExecutionHooks 默认空实现 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hooks_on_step_before_returns_noskip():
    hooks = ExecutionHooks()
    result = await hooks.on_step_before(step={}, context={})
    assert isinstance(result, StepHookResult)
    assert result.skip is False


@pytest.mark.asyncio
async def test_hooks_on_step_after_does_not_raise():
    hooks = ExecutionHooks()
    await hooks.on_step_after(step={}, output={}, context={})


@pytest.mark.asyncio
async def test_hooks_on_run_start_does_not_raise():
    hooks = ExecutionHooks()
    await hooks.on_run_start(run_id="r1", context={})


@pytest.mark.asyncio
async def test_hooks_on_run_end_does_not_raise():
    hooks = ExecutionHooks()
    await hooks.on_run_end(run_id="r1", context={})


# ── 异常隔离（五条约定之三）—— 验证子类异常不影响调用方 ──────────────────────

class BrokenHooks(ExecutionHooks):
    async def on_step_after(self, step, output, context):
        raise RuntimeError("hook 崩溃了")


@pytest.mark.asyncio
async def test_hook_exception_isolation():
    """Runner 应对异常进行隔离；此处验证异常确实会被抛出（由 Runner 负责 try/except）。"""
    hooks = BrokenHooks()
    with pytest.raises(RuntimeError, match="hook 崩溃了"):
        await hooks.on_step_after(step={}, output={}, context={})
