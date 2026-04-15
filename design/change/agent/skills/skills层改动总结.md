# skills层改动总结

- 新增文件：skills/base.py（Skill 基类 + LLMAgentSpec + IOSkillSpec + FlowSkillSpec）、skills/llm/types.py（Defect + EvaluatorReport，[待定]）
迁移并重构：

    1. atomic/llm_planner_call.py → llm/planner.py（继承 LLMAgentSpec，元数据声明，返回 dict 而非 JSON 字符串）
    2. atomic/llm_generator_call.py → llm/generator.py（消灭文本往返，Literal 枚举 action，SkillCard 注入，删 _validate_actions）
    3. atomic/llm_evaluator_call.py → llm/evaluator.py（接受 WorkflowModel 扫描，Prompt 外置，强化静态扫描约束表达）
    4. atomic/llm_prompt_call.py → llm/prompt.py（删 Mock 模式，统一 execute_step，print → logger）
    5. atomic/sub_workflow_call.py → flow/sub_workflow_call.py（修复依赖方向，输入校验改造，VariableMappingError 处理）
    6. atomic/file_reader.py → io/file_reader.py（统一 execute_step，从 step.inputs 读取）
    7. atomic/file_writer.py → io/file_writer.py（删手动变量替换，目录自动创建，统一 execute_step）

- 删除或迁移：dummy_evaluator.py 移到 tests/fixtures/

- skills/__init__.py 和 skills/llm/__init__.py 等
    各层目录的 __init__.py 都是空文件，保持空文件，只做 Python 包标记，不做任何 import。SkillRegistry 的递归扫描通过 rglob("*.py") 自动发现所有 skill 文件，不依赖 __init__.py 里的任何声明