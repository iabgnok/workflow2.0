"""单元测试：ConditionEvaluator（任务 2.2）"""
import pytest
from agent.engine.condition_evaluator import ConditionEvaluator


@pytest.fixture
def evaluator():
    return ConditionEvaluator()


def test_none_condition_no_skip(evaluator):
    skip, reason = evaluator.eval(None, {})
    assert skip is False
    assert reason == ""


def test_truthy_condition_no_skip(evaluator):
    skip, reason = evaluator.eval("retry_count > 0", {"retry_count": 1})
    assert skip is False
    assert reason == ""


def test_falsy_condition_skips(evaluator):
    skip, reason = evaluator.eval("retry_count > 0", {"retry_count": 0})
    assert skip is True
    assert "条件不满足" in reason
    assert "retry_count > 0" in reason


def test_name_not_defined_skips(evaluator):
    skip, reason = evaluator.eval("undefined_var > 0", {})
    assert skip is True
    assert "条件变量未就绪" in reason


def test_invalid_expression_does_not_skip(evaluator):
    """InvalidExpression → 不跳过，默认执行（Decision 4）。"""
    skip, reason = evaluator.eval("%%%invalid%%%", {})
    assert skip is False


def test_empty_context_with_false_literal_skips(evaluator):
    skip, reason = evaluator.eval("False", {})
    assert skip is True


def test_true_literal_no_skip(evaluator):
    skip, reason = evaluator.eval("True", {})
    assert skip is False
