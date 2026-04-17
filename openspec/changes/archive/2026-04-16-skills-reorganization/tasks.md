## 1. 技能基类创建

- [x] 1.1 创建 `new_src/agent/skills/__init__.py`
- [x] 1.2 创建 `new_src/agent/skills/base.py`，实现 `Skill[InputT, OutputT]` 泛型基类
- [x] 1.3 实现 `LLMAgentSpec` 子类（_get_structured_llm, _load_system_prompt, system_prompt_path, default_temperature）
- [x] 1.4 实现 `IOSkillSpec` 和 `FlowSkillSpec` 语义分组子类
- [x] 1.5 实现 `schema_summary()` 类方法
- [x] 1.6 编写基类单元测试

## 2. LLM 技能迁移

- [x] 2.1 创建 `new_src/agent/skills/llm/__init__.py`
- [x] 2.2 迁移 Generator → `llm/generator.py`（继承 LLMAgentSpec，元数据声明，消除文本往返：StructuredWorkflowArtifact → WorkflowModel）
- [x] 2.3 迁移 Evaluator → `llm/evaluator.py`（继承 LLMAgentSpec，静态扫描改为接受 WorkflowModel，四维评分外化）
- [x] 2.4 迁移 Planner → `llm/planner.py`（继承 LLMAgentSpec，返回 dict 非 JSON 字符串，系统 Prompt 外部化）
- [x] 2.5 迁移 Prompt → `llm/prompt.py`（继承 LLMAgentSpec，删除 Mock 模式，统一 execute_step）
- [x] 2.6 编写 LLM 技能的单元测试

## 3. IO 技能迁移

- [x] 3.1 创建 `new_src/agent/skills/io/__init__.py`
- [x] 3.2 迁移 FileReader → `io/file_reader.py`（继承 IOSkillSpec，从 step.inputs 读取路径）
- [x] 3.3 迁移 FileWriter → `io/file_writer.py`（继承 IOSkillSpec，删除手动变量替换，自动创建目录）
- [x] 3.4 编写 IO 技能的单元测试

## 4. Flow 技能迁移

- [x] 4.1 创建 `new_src/agent/skills/flow/__init__.py`
- [x] 4.2 迁移 SubWorkflowCall → `flow/sub_workflow_call.py`（继承 FlowSkillSpec，修复 import 路径，增强输入校验）
- [x] 4.3 编写 Flow 技能的单元测试

## 5. 清理

- [x] 5.1 将 `dummy_evaluator.py` 迁移到 `tests/fixtures/`
- [x] 5.2 确认 `skills/atomic/` 不再有任何引用
- [x] 5.3 运行全部技能测试确认无回归
