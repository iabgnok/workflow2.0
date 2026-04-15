# MyWorkflow 设计档案 · 01 · 架构与目录

> 读前置:00 · 顶层概览
> 本文档目标:把"系统由哪些层构成、每层职责是什么、依赖方向如何"说清楚,让任何人(或 LLM)能据此重建一个等价系统的骨架。

---

## 1. 八层架构总图

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ① 入口与配置层  cli.py / main.py / config/settings.py                  │
│       │                                                                  │
│       ▼  组装 Runner、传入参数                                           │
├─────────────────────────────────────────────────────────────────────────┤
│  ② 协调层(Runner + 拆分子模块)                                          │
│       runner.py(薄编排器,目标 ≤ 150 行)                                │
│       step_executor.py / condition_evaluator.py /                        │
│       resume_strategy.py / execution_hooks.py / execution_observer.py    │
│       │              ▲                                                    │
│       │              │ ExecutionHooks 注入                               │
│       │              │                                                    │
│       │              └────────── ⑤ 业务编排层 ─────────┐                │
│       │                          champion_tracker.py    │                │
│       │  ┌───── ③ 协议层(确定性规则唯一来源)─────┐  │                │
│       │  │  models / gatekeeper / dry_run /         │  │                │
│       │  │  security_scan / runtime_assertions /    │  │                │
│       │  │  normalizer / service / report / errors  │  │                │
│       │  └──────────────────────────────────────────┘  │                │
│       │  ┌───── ④ 能力层(Skills + AgentSpec)────────┐│                │
│       │  │  llm/ (planner/generator/evaluator/prompt) ││                │
│       │  │  io/  (file_reader / file_writer)          ││                │
│       │  │  flow/(sub_workflow_call)                  ││                │
│       │  └────────────────────────────────────────────┘│                │
│       ▼                                                  ▼                │
├─────────────────────────────────────────────────────────────────────────┤
│  ⑥ 基础设施层  infra/                                                    │
│       state_store / llm_factory / llm_client_registry /                  │
│       workflow_registry / context_manager / variable_mapper /            │
│       error_policy                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                              │                  ▲
                              ▼                  │
┌─────────────────────────────────────────────────────────────────────────┐
│  ⑦ 工作流资源层  workflows/                                              │
│       meta/ (内置元工作流) / dev/ (LLM 生成产物) /                       │
│       registry/ (index.json) / templates/ (few-shot 示例)                │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ⑧ 测试层  tests/  unit / integration / e2e / fixtures                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. 依赖方向严格单向

```
①入口 → ②协调 → {③协议, ④能力, ⑥基础设施}
②协调 ↔ ⑤业务编排  (通过 ExecutionHooks 接口,业务编排层不被 import)
④能力 → ⑥基础设施 (LLM 调用)
⑤业务编排 → ⑥基础设施 (StateStore 写 champion_json/run_meta)
③协议 → 无外部依赖(零业务、零 LLM、零 IO,纯逻辑)
⑥基础设施 → 外部(LLM API / SQLite / 文件系统)
⑦工作流资源 是数据,被②③⑥读写,自己不依赖任何代码层
⑧测试 覆盖所有层,自己不被任何层 import
```

**最重要的反向禁止:**
- 协议层 ③ 永远不 import 协调层 / 能力层 / 业务编排层(否则协议层就被业务污染)
- 能力层 ④ 永远不 import 协调层 / 业务编排层(否则 Skill 知道自己被谁调用,违反单一职责)
- 基础设施层 ⑥ 永远不 import 任何上层(否则形成隐式循环依赖)

## 3. 各层详细职责

### 层 ① 入口与配置层

**职责:** CLI 参数解析、环境变量统一加载、Runner 实例组装、执行启动。

**为什么单独做一层:** 让"如何启动"和"启动后做什么"分离,使入口可独立测试,使切换启动方式(CLI / API / 测试)不需改业务代码。

**模块:**
- `cli.py`:命令行入口,提供 `run` / `replay` / `list` 子命令
- `main.py`:程序主入口,组装 Runner
- `config/settings.py`:所有环境变量、阈值、常量的唯一来源(用 pydantic-settings 类型化)

**禁止:** 这一层不能写任何业务逻辑或执行逻辑。

---

### 层 ② 协调层(Runner)

**职责:** 驱动步骤循环的薄编排器。读取步骤列表 → 调用 ConditionEvaluator → 调用 StepExecutor → 处理结果 → 更新 ExecutionContext → 循环。

**为什么单独做一层:** Runner 是系统的"心脏"。当前(重构前)它是 691 行的上帝类,承担了循环编排、Champion 业务逻辑、注册回放、context 压力观测等互不相关的职责。重构后目标 ≤ 150 行,通过 ExecutionHooks 接收业务注入,引擎本体对内容无感知。

**子模块:**

| 模块 | 职责 | 行数目标 |
|------|------|---------|
| `runner.py` | 薄编排器,主循环 | ≤ 150 |
| `step_executor.py` | 单步执行(skill 查找 + execute_with_policy + 输出写回 context)| ~80 |
| `condition_evaluator.py` | simpleeval 沙盒条件求值,独立可测试 | ~40 |
| `resume_strategy.py` | 断点续传(load state → hydrate context → 确定 start_step_id)| ~60 |
| `execution_hooks.py` | Hook 接口定义(Protocol)| ~30 |
| `execution_observer.py` | context 压力采样 + telemetry | ~70 |
| `parser.py` | 仅处理手写 `.step.md`(LLM 生成物不经此)| ~170 |

**关键设计:**
- `ExecutionContext` 三层分离:
  - `state: dict[str, Any]` — 业务变量(workflow_blueprint, final_artifact 等)
  - `meta: RunMeta` — 元数据(run_id, workflow_name, escalation_level)
  - `runtime: RuntimeState` — 运行时状态(chat_history, prev_defects)

- `Runner.run()` 是入口,可选传入 `run_id` 触发断点续传
- 主循环每步必经五个守卫:condition / pre-assertion / execute / post-assertion / persist
- on_reject 跳转由 Runner 解释执行,不下放给 LLM

---

### 层 ③ 协议层(确定性规则唯一来源)

**职责:** 所有"可由代码确定地判定对错"的规则的唯一实现处。只消费 `WorkflowModel`(Pydantic 对象),零业务依赖,零 LLM 调用,零 IO。

**为什么单独做一层:** 协议层是 MyWorkflow 区别于其他 Agent 框架的核心创新点。把规则集中,意味着:
- 规则变更只改一处,不会出现"三处定义不一致"的 bug
- 规则可以被测试(纯函数,纯类型,易构造测试用例)
- 协议层可以被多个上游消费(Runner / WorkflowRegistry / Evaluator 都查它)

**模块清单:**

| 模块 | 职责 |
|------|------|
| `models.py` | `WorkflowModel / WorkflowStep / WorkflowMetadata` — 系统的"内部真理" |
| `gatekeeper.py` | 硬规则:action 在白名单 / on_reject < 当前 id / outputs 非空 / step_id 不重复 / IO 标题单数 |
| `dry_run.py` | 变量依赖图模拟执行,检测未解析变量和步骤可达性 |
| `security_scan.py` | 危险关键词扫描 / `[DANGER]` `[CONFIRM]` 标记审计 |
| `runtime_assertions.py` | 执行前后对 step inputs/outputs 做契约断言 |
| `normalizer.py` | 归一化(`**Inputs**` → `**Input**`)+ legacy DSL 兼容 |
| `service.py` | `ProtocolService` 统一入口,编排 parse → schema → gatekeeper → dry_run |
| `report.py` | `ProtocolReport` 统一错误结构 |
| `errors.py` | `ProtocolSchemaError / ProtocolGatekeeperError / ProtocolDryRunError` 异常类 |
| `error_codes.py` | 协议错误码常量表(版本化) |
| `infer_inputs.py` | 推断工作流的最小必需 inputs(用于 dry_run 容错) |

**详见:02 · 协议层与 DSL**

---

### 层 ④ 能力层(Skills + AgentSpec)

**职责:** 每个 Skill 是自描述的执行单元,声明自己的 Prompt 模板、输入输出类型、幂等性、重试策略、SkillCard 元数据。

**为什么单独做一层:** 能力层是"做事的人",和"指挥的人"(协调层)、"立法的人"(协议层)分离。每个 Skill 的"全部知识"集中在一处。

**子目录组织(重构后):**

```
skills/
├── base.py                  # Skill 抽象基类 + AgentSpec(Prompt+类型+元数据)
├── llm/
│   ├── planner.py           # PlannerSpec
│   ├── generator.py         # GeneratorSpec(直出 WorkflowModel)
│   ├── evaluator.py         # EvaluatorSpec(含四维 rubric 引用)
│   └── prompt.py            # 通用 LLM 调用
├── io/
│   ├── file_reader.py
│   └── file_writer.py
└── flow/
    └── sub_workflow_call.py
```

**AgentSpec 的标准声明(自描述):**

```python
class GeneratorSpec(LLMAgentSpec):
    name = "llm_generator_call"
    description = "基于 WorkflowBlueprint 生成可执行的 WorkflowModel"
    when_to_use = "接到 Planner 蓝图后,生成或修复工作流"
    do_not_use_when = "需要执行已生成工作流时(用 sub_workflow_call)"
    
    input_type = GeneratorInput
    output_type = WorkflowModel
    
    idempotency = IdempotencyLevel.L0
    retry_policy = RetryPolicy(max_retries=2, backoff=2.0)
    
    system_prompt_path = "prompts/generator_system_v1.md"
    user_prompt_template = GENERATOR_PROMPT_TEMPLATE
```

**SkillCard:** 每个 AgentSpec 暴露的元数据子集(`name / description / when_to_use / do_not_use_when / input_schema / output_schema`),由 SkillRegistry 聚合成 `skill_manifest`,注入 Generator Prompt 替代纯名称列表——这是消灭"LLM 误用技能"的根本解。

---

### 层 ⑤ 业务编排层

**职责:** Meta Workflow 专属的业务逻辑,通过 ExecutionHooks 接入 Runner。

**为什么单独做一层:** Champion 机制是 Meta Workflow 的业务规则,不是引擎的通用能力。把它从 Runner 拆出,意味着普通工作流运行时这些逻辑完全不存在,Meta Workflow 启动时才注入——这是铁律七的物理保证。

**核心模块:**
- `champion_tracker.py`:Champion 竞选逻辑
  - `requirement_fingerprint` / `blueprint_fingerprint` 计算
  - Champion 更新(score 比较,只保留更优产物)
  - `handoff_artifact` 构建(用于 ContextManager hard reset 后的状态交接)

**双指纹机制:**
- `requirement_fingerprint = sha256(requirement)` — 用户原始需求的指纹
- `blueprint_fingerprint = sha256(planner_output_canonical_json)` — Planner 输出蓝图的指纹
- Champion 表按 (req_fp, bp_fp) 联合主键存,命中时直接复用,跳过 Generator + Evaluator,**省时 + 省 token**

---

### 层 ⑥ 基础设施层

**职责:** 所有外部依赖的适配器,可替换,不承载业务逻辑。

**模块清单:**

| 模块 | 职责 |
|------|------|
| `state_store.py` | `AbstractStateStore` 接口 + SQLite 默认实现 |
| `llm_factory.py` | `build_chat_model` / `build_structured_output_model` 工厂 |
| `llm_client_registry.py` | LLM 客户端单例化,按 (provider, model, temperature, json_mode) 缓存 |
| `workflow_registry.py` | 注册索引管理,只写已通过协议层的 WorkflowModel |
| `context_manager.py` | token 压力估算 + soft/hard reset |
| `variable_mapper.py` | 父子工作流变量映射 |
| `error_policy.py` | 三级幂等性策略 + tenacity 重试包装 |

**关键设计:**
- StateStore 用 SQLite,所有状态序列化为 JSON 存储,**不依赖 pickle**(避免对象不可序列化整包丢失)
- LLM 客户端单例化,复用 httpx 连接池,显著减少冷启动延迟
- error_policy 的 `execute_with_policy` 是所有 Skill 调用的统一包装

---

### 层 ⑦ 工作流资源层

**职责:** `.step.md` 文件和注册索引,是数据而不是代码。

**目录结构:**

```
workflows/
├── meta/                              # 系统内置元工作流
│   ├── main_workflow.step.md          # Meta Main Workflow 主链路
│   ├── workflow_planner.step.md
│   ├── workflow_designer.step.md
│   └── quality_evaluator.step.md
├── dev/                               # LLM 生成的工作流产物
│   └── <auto-named>.step.md
├── registry/
│   └── index.json                     # 注册索引(独立存放,便于备份/迁移)
└── templates/                         # few-shot 示例,被 Generator Prompt 引用
    ├── example_linear.step.md
    └── example_with_on_reject.step.md
```

**为什么 index.json 独立存放:** 让数据(`.step.md`)和元数据(索引)生命周期解耦,支持多索引、备份、迁移、一致性检查(详见重构补充 5)。

---

### 层 ⑧ 测试层

```
tests/
├── unit/           # 单模块测试,mock 所有外部依赖
├── integration/    # 多模块联动,含协议层 gate 测试
├── e2e/            # 真实 LLM 调用,有网络隔离标记
└── fixtures/       # 测试用 .step.md 样本统一管理
```

**协议层 gate 测试是必跑项**:
- `test_m3_closure_gates.py`:协议层闭环治理守护
- `test_dsl_cutover_gates.py`:DSL 切换守护

---

## 4. 关键文件一览(给"我要复现这个系统"的 LLM)

如果要从零复现 MyWorkflow,**最小可用集合**为以下文件,按依赖顺序:

```
1. agent/engine/protocol/error_codes.py        # 错误码常量(无依赖)
2. agent/engine/protocol/report.py             # ProtocolReport(依赖 error_codes)
3. agent/engine/protocol/models.py             # WorkflowModel(依赖 pydantic)
4. agent/engine/protocol/normalizer.py         # 归一化(依赖 models)
5. agent/engine/protocol/gatekeeper.py         # 硬规则(依赖 models, report)
6. agent/engine/protocol/dry_run.py            # 变量依赖图(依赖 models, report)
7. agent/engine/protocol/security_scan.py      # 危险扫描(依赖 report)
8. agent/engine/protocol/runtime_assertions.py # 运行时断言(依赖 models)
9. agent/engine/protocol/service.py            # ProtocolService 入口
10. agent/engine/parser.py                     # WorkflowParser
11. agent/engine/state_store.py                # SQLite StateStore
12. agent/engine/skill_registry.py             # SkillRegistry + 扫描
13. agent/engine/error_policy.py               # 三级幂等 + tenacity
14. agent/engine/llm_factory.py                # LLM 客户端工厂
15. agent/engine/context_manager.py            # 压力估算
16. agent/engine/workflow_registry.py          # 注册索引
17. agent/skills/atomic/file_reader.py         # 最简 Skill 示范
18. agent/skills/atomic/file_writer.py         # 写入 Skill(L1 幂等)
19. agent/skills/atomic/llm_prompt_call.py     # 通用 LLM 调用 Skill
20. agent/skills/atomic/llm_planner_call.py    # Planner Skill
21. agent/skills/atomic/llm_generator_call.py  # Generator Skill
22. agent/skills/atomic/llm_evaluator_call.py  # Evaluator Skill
23. agent/skills/atomic/sub_workflow_call.py   # 子工作流调用 Skill
24. agent/engine/runner.py                     # Runner 主循环(最复杂)
25. agent/workflows/meta/*.step.md             # 四个内置元工作流
26. main.py                                    # 入口
```

按这个顺序写,每写完一个模块都能用 unit 测试覆盖,直到 24 才需要全链路。

## 5. 数据类型流图(全链路类型边界)

```
   用户输入 (str / dict)
        │
        ▼
   RunInput ────────────────── (Pydantic,入口校验)
        │
        ▼
   ExecutionContext ────────── { state: dict, meta: RunMeta, runtime: RuntimeState }
        │
   ┌────┴────┐
   ▼         ▼
 Planner   Parser
   │         │
   ▼         ▼
 WorkflowBlueprint        WorkflowModel ── (Pydantic,内部真理)
        │                         │
        ▼                         ▼
    Generator                ProtocolService
        │                    ┌────┼────┐
        ▼                    ▼    ▼    ▼
   WorkflowModel(直出)  Gatekeeper DryRun SecurityScan
        │                    └────┬────┘
        ▼                         ▼
    Evaluator <─────── ProtocolReport (统一错误结构)
        │
        ▼
   EvaluatorReport (Pydantic,含 status/defects/scores)
        │
        ▼
   StepExecutor 写回 ExecutionContext.state
        │
        ▼
   StateStore.save_step_state ── 持久化
```

每个箭头都是一次类型边界,Pydantic 在每个边界做校验,不允许 `Any` 无声穿越。

## 6. 重构前后对照

如果要描述当前快照与目标的 delta:

| 维度 | 重构前(当前快照) | 重构后(目标) |
|------|----------------|--------------|
| Runner 行数 | 691 行 | ≤ 150 行 |
| 上帝类问题 | Runner 同时承担循环/Champion/注册/观测 | Runner 只做循环,其他通过 Hook |
| Generator 输出 | LLM → render_markdown → Parser → dict(文本往返)| Generator 直出 WorkflowModel |
| action 检查位置 | gatekeeper / security_scan / generator 三处 | 仅 gatekeeper(单点归属)|
| `_normalize_name` | gatekeeper 和 dry_run 各一份 | `protocol/utils.py` 共用 |
| 业务逻辑硬编码 | `if workflow_name == "Meta Main Workflow"` | ExecutionHooks 注入 |
| Skill 元数据 | 散落在 error_policy 字典 + Skill 类 | AgentSpec 集中声明 |
| Prompt 位置 | Python 字符串常量 | `prompts/*.md` 外置文件 |

---

→ 接下来阅读 **02 · 协议层与 DSL** 了解最核心的工程创新。
