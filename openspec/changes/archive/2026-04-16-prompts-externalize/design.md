## Context

Prompt 工程是 MyWorkflow 质量的关键杠杆。当前 Prompt 嵌入代码中，修改一个措辞需要改 Python 文件、重新部署。外部化后可以独立于代码演进。

## Goals / Non-Goals

**Goals:**
- 三个系统 Prompt 独立为 Markdown 文件
- 版本化命名（_v1/_v2）支持审计追踪
- LLMAgentSpec._load_system_prompt() 提供统一加载和缓存

**Non-Goals:**
- 不引入 Prompt 模板引擎（Jinja2 等），动态部分仍用 Python f-string/PromptTemplate
- 不改变 Prompt 的实际内容策略（措辞优化是后续任务）
- 不引入 Prompt A/B 测试框架

## Decisions

### Decision 1: Markdown 格式而非 YAML/JSON
**选择**: .md 文件
**理由**: Prompt 本质是自然语言文本，Markdown 可读性最好，支持标题/列表/代码块格式。LLM 原生理解 Markdown。

### Decision 2: 版本化命名而非 Git 版本控制
**选择**: 文件名含版本号（_v1, _v2）
**理由**: 允许新旧版本同时存在（灰度切换），比纯靠 Git diff 更直观。代码中 system_prompt_path 明确指向版本号，不会意外使用错误版本。

## Risks / Trade-offs

- **[Risk] 文件路径硬编码**: system_prompt_path 写死了文件名。→ **Mitigation**: 路径通过 settings.prompts_root 前缀拼接，只有文件名在技能代码中声明。
