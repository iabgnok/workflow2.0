## Why

当前三个 LLM 技能（Generator、Evaluator、Planner）的系统 Prompt 以硬编码字符串的形式内嵌在 Python 代码中。这导致：Prompt 修改需要改 Python 文件、版本演进无法独立追踪、Prompt 长度增加后代码可读性下降。需要将系统 Prompt 外部化到独立的 Markdown 文件中。

## What Changes

- **新增 `prompts/` 目录**
- **新增 `generator_system_v1.md`**：Generator 系统 Prompt（角色定义、DSL 格式规则、变量命名、少样本示例、技能白名单、修复模式规则、禁止行为）
- **新增 `evaluator_system_v1.md`**：Evaluator 系统 Prompt（角色定义、四维评分硬规则、逻辑完备性评分细则、安全评分细则、输出契约）
- **新增 `planner_system_v1.md`**：Planner 系统 Prompt（角色定义、拆分判断、输出字段规范、禁止行为）
- 版本化命名（`_v1`），未来升级创建 `_v2` 文件，旧版本短暂保留

## Capabilities

### New Capabilities
- `external-prompts`: 外部化的 LLM 系统 Prompt 文件，版本化管理，通过 LLMAgentSpec._load_system_prompt() 加载并缓存

### Modified Capabilities

## Impact

- 三个 LLM 技能的 `system_prompt_path` 字段指向 `prompts/` 目录下的文件
- Prompt 修改不再需要改 Python 代码
- 动态部分（skill_manifest、blueprint、prev_defects）仍在 Python 的 PromptTemplate 中
