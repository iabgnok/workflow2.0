## Why

当前技能层（`agent/skills/atomic/`）是一个扁平目录，所有 9 个技能文件混在一起，没有统一的基类或元数据声明。每个技能的名称、描述、幂等性级别、重试策略都由外部代码（error_policy.py）硬编码管理，添加新技能需要改多个文件。需要引入统一的技能基类和分类目录结构，让每个技能成为自描述的独立单元。

## What Changes

- **新增 `skills/base.py`**：定义 `Skill[InputT, OutputT]` 泛型基类，子类 `LLMAgentSpec`、`IOSkillSpec`、`FlowSkillSpec`。类变量声明：name, description, when_to_use, do_not_use_when, idempotency, retry_policy, input_type, output_type。`schema_summary()` 类方法生成 SkillCard 文本。
- **目录重组**：
  - `atomic/llm_generator_call.py` → `llm/generator.py`（继承 LLMAgentSpec，核心变更：消除文本往返，LLM 直接输出 StructuredWorkflowArtifact → WorkflowModel）
  - `atomic/llm_evaluator_call.py` → `llm/evaluator.py`（静态扫描改为接受 WorkflowModel，四维评分体系外化到 Prompt）
  - `atomic/llm_planner_call.py` → `llm/planner.py`（系统 Prompt 外部化，返回 dict 而非 JSON 字符串）
  - `atomic/llm_prompt_call.py` → `llm/prompt.py`（删除 Mock 模式，统一 execute_step 接口）
  - `atomic/file_reader.py` → `io/file_reader.py`（从 step.inputs 读取变量）
  - `atomic/file_writer.py` → `io/file_writer.py`（删除手动变量替换，自动创建目录）
  - `atomic/sub_workflow_call.py` → `flow/sub_workflow_call.py`（修复依赖方向，增强输入校验）
  - `atomic/dummy_evaluator.py` → `tests/fixtures/`（测试工具不应在生产代码里）

## Capabilities

### New Capabilities
- `skill-base-class`: 统一技能基类体系，自描述元数据，泛型类型约束
- `skill-llm-agents`: LLM 类技能（Generator、Evaluator、Planner、Prompt）的重构实现
- `skill-io-agents`: IO 类技能（FileReader、FileWriter）的重构实现
- `skill-flow-agents`: 流程类技能（SubWorkflowCall）的重构实现

### Modified Capabilities

## Impact

- `skills/atomic/` 目录废弃，替换为 `skills/llm/`、`skills/io/`、`skills/flow/` 三个子目录
- SkillRegistry 的扫描路径需从 `atomic/` 改为递归子目录扫描（在 infra-layer-extract 变更中处理）
- error_policy.py 的硬编码策略字典可被技能自身的 retry_policy 声明替代
- Generator 的核心变更（消除文本往返）是方向一的关键落地点
