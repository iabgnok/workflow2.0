## Context

技能是 MyWorkflow 的执行单元，当前 9 个技能混在 `skills/atomic/` 平铺目录中。重构后按语义分类为三个子目录，并引入统一基类让每个技能成为自描述单元。这是重构"方向三：统一 Skill 元数据"的核心实现。

## Goals / Non-Goals

**Goals:**
- 定义统一的 Skill 基类体系（Skill → LLMAgentSpec / IOSkillSpec / FlowSkillSpec）
- 每个技能声明自己的 name、description、when_to_use、idempotency、retry_policy
- Generator 消除文本往返：LLM 输出 StructuredWorkflowArtifact → 直接转换 WorkflowModel
- Evaluator 静态扫描改为接受 WorkflowModel
- 所有 LLM 技能的系统 Prompt 外部化到 `prompts/` 目录
- `schema_summary()` 生成 SkillCard 文本，供 Generator Prompt 注入

**Non-Goals:**
- 不改变技能的对外接口（execute_step(step, context) → dict）
- 不新增技能，只迁移和增强现有技能
- 不改变 simpleeval 条件求值逻辑（那是 engine 层）
- 不改变 EvaluatorReport 的评分维度和权重

## Decisions

### Decision 1: 泛型 Skill[InputT, OutputT] 而非简单基类
**选择**: Generic 基类，允许子类声明输入输出类型
**理由**: schema_summary() 可自动从 Pydantic schema 生成描述，无需手写。SkillRegistry 可自动收集类型信息构建 manifest。

### Decision 2: LLMAgentSpec 提供 _get_structured_llm() 和 _load_system_prompt()
**选择**: 在基类中提供 LLM 交互的公共方法
**理由**: 四个 LLM 技能都需要构建 structured output LLM 和加载系统 Prompt，提取到基类避免重复。

### Decision 3: Generator 输出 WorkflowModel 而非 Markdown
**选择**: StructuredWorkflowArtifact → WorkflowModel（直接类型转换，不经过 Markdown 渲染再解析）
**理由**: 这是"方向一：全链路数据类型化"的核心。消除文本往返后：无需 normalizer 清洗 LLM 格式问题、变量类型在边界处被 Pydantic 捕获、Runner 不需要防御性解析。

### Decision 4: StructuredWorkflowArtifact 的 action 字段用 Annotated[str, AfterValidator] 而非 Literal
**选择**: 动态校验而非静态枚举
**理由**: 技能列表是运行时确定的（SkillRegistry 扫描结果），无法在类型定义时确定。使用 AfterValidator 在实例化时校验 action 是否在已注册列表中。

### Decision 5: EvaluatorReport / Defect 类型定义放在 skills/llm/types.py（已决策）
**选择**: 新建 `skills/llm/types.py`，集中放置 `EvaluatorReport`、`Defect`、`StructuredWorkflowArtifact` 等 LLM 技能层的类型定义
**理由**: EvaluatorReport 是 Evaluator 技能的输出类型，Defect 是其子结构。放在技能层而非协议层，因为它们描述的是 LLM 评审结果的业务语义，不属于协议层的确定性规则。协议层通过 `report.py` 的 `errors_as_defects()` 产出兼容格式，但类型归属在技能层。

### Decision 6: SubWorkflowCall 返回值统一使用 sub_ 前缀（已决策）
**选择**: 子工作流的输出变量写回父 context 时，统一添加 `sub_` 前缀
**理由**: 防止子工作流输出覆盖父 context 的同名变量。设计文档中 `variable_mapper.py` 的 output mapping 已隐含此约定，此处显式冻结。前缀由 VariableMapper 在 output mapping 阶段自动添加，技能代码和工作流 DSL 中不需要手动声明。

## Risks / Trade-offs

- **[Risk] Generator 结构化路径是最复杂的单点变更**: 涉及 LLM 输出格式、Prompt 工程、类型转换。→ **Mitigation**: 保留 to_markdown() 作为持久化方法，确保可回退到文本路径。
- **[Risk] 旧版 skill 接口兼容性**: 某些技能可能有 execute(text, context) 的旧接口。→ **Mitigation**: SkillRegistry 的 _build_instance() 保持 fallback 逻辑。
