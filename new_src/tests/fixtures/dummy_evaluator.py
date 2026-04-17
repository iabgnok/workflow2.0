"""测试用虚拟 Evaluator。

仅用于集成测试和 Runner 测试，不应出现在生产代码路径中。
"""
import logging

logger = logging.getLogger(__name__)


class DummyevaluatorCall:
    """模拟 Evaluator 行为的测试桩：

    - 步骤名称为 "Mock Evaluator" 时返回 REJECTED
    - 其他情况返回 Dummy Output
    """

    async def execute_step(self, step: dict, context: dict) -> dict:
        if step.get("name") == "Mock Evaluator":
            return {
                "evaluator_report": {"status": "REJECTED", "defects": "Bad standard code."},
                "escalation_level": context.get("escalation_level", 0),
            }
        return {"generated_code": "Dummy Output"}
