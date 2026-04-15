# dummy_evaluator.py 的命运

## 一、搬移到测试目录

dummy_evaluator.py 是纯测试用的 mock skill，用于测试 Escalation Ladder 而不需要真实 LLM 调用。它不应该出现在 skills/ 生产代码目录里。
重构后迁移到 tests/fixtures/skills/dummy_evaluator.py，在需要它的测试里通过 SkillRegistry.register() 手动注入，不走自动扫描路径。