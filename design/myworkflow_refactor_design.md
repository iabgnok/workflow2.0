# MyWorkflow 重构设计纲领

> 版本：Refactor v1.0  
> 状态：设计基线（基于 V1–V4 演进历史 + 全链路架构审计）  
> 适用范围：指导本次重构的全部开发决策，不替代各模块的详细设计文档

---

## 目录

1. [项目定位与底线目标](#1-项目定位与底线目标)
2. [从历史教训提炼的铁律](#2-从历史教训提炼的铁律)
3. [重构的三大方向](#3-重构的三大方向)
4. [分层架构设计](#4-分层架构设计)
5. [项目目录结构](#5-项目目录结构)
6. [业务流程链路图](#6-业务流程链路图)
7. [LLM 权力边界与幻觉控制](#7-llm-权力边界与幻觉控制)
8. [约束规则的归属原则](#8-约束规则的归属原则)
9. [其他优化事项与优先级](#9-其他优化事项与优先级)
10. [协议冻结与变更治理](#10-协议冻结与变更治理)

---

## 1. 项目定位与底线目标

### 1.1 一句话定位

MyWorkflow 是一个以 Markdown DSL（`.step.md`）为工作流格式、以三角色 LLM 闭环为生成引擎、以协议层为治理中枢、以 Runner 为执行状态机的**工作流自动生成与执行系统**。

系统本身即是一个工作流：接收自然语言需求，输出可被本引擎重复执行的标准化 `.step.md` 工作流。

### 1.2 四条不可妥协的底线

```
底线 1：生成的工作流必须可被本引擎正确运行，能完成用户需求——不是"生成了"，是"可运行"
底线 2：安全检查（静态扫描 + 运行时拦截）必须能阻断危险操作——代码判定，不交给 LLM
底线 3：上下文与状态持久化必须可恢复——崩溃后按 run_id 恢复，不允许整包丢弃
底线 4：所有可以由代码确定性验证的事情，绝对不交给 LLM 判断
```

### 1.3 设计哲学

- **确定性优先**：能用代码判定的规则，代码做；语义性问题才交给 LLM
- **协议先行**：规则归属集中在 protocol 层，业务层只消费结果
- **类型驱动**：整条数据流上的每个边界都有 Pydantic 类型，不允许 `Any` 无声穿越
- **引擎无感知内容**：Runner 不能知道任何具体工作流名字或业务逻辑，通过 Hook 接收业务注入
- **治理可执行**：所有治理要求必须落到可跑的测试闸门，不是文字约定

---

## 2. 从历史教训提炼的铁律

这些铁律来自 V1–V4 的真实踩坑，在重构中作为硬约束写入设计，不允许例外。

### 铁律一：路由权在 Runner，不在 LLM

禁止 LLM 通过输出 `__jump_to__` 等字段决定主流程跳转。步骤级 `on_reject` 在 `.step.md` 中声明，Runner 解释执行。LLM 只生成内容，不控制流。

### 铁律二：未知 Skill 必须硬失败

Action 必须命中 SkillRegistry 注册白名单。未知技能直接抛出 `SkillNotFoundError`，进入 ErrorPolicy 处理，不允许软跳过或静默继续。

### 铁律三：协议规则必须单点归属

Schema、Gatekeeper、DryRun、ErrorCodes 统一归属 `protocol/` 层。Runner 和 WorkflowRegistry 不再新增协议判断分支，只消费协议层结果。任何协议变更必须在协议层改，必须有测试证据。

### 铁律四：注册前必须验证执行契约

注册顺序固定为：`Gatekeeper → DryRun → Write Index`。任一失败必须保证 no dirty write（无 dev 稿残留、无索引脏条目）。

### 铁律五：恢复能力必须可证明

运行上下文持久化必须支持按 run_id 恢复。context 三层（state/meta/runtime）必须有类型保障，不允许序列化失败整包丢弃。

### 铁律六：治理策略必须测试化

DSL 切换、注册闸门、Prompt 契约必须有对应 gate 测试持续守护。协议变更必须先登记后合入。

### 铁律七（新增）：引擎不知道任何具体工作流

Runner 不再通过 `workflow_name == "Meta Main Workflow"` 字符串判断来激活业务逻辑。所有业务行为（champion 更新、注册触发）通过 `ExecutionHooks` 注入，引擎本体对内容无感知。

### 铁律八（新增）：LLM 生成物走结构化路径，不经文本往返

Generator 输出 `WorkflowModel`（Pydantic 对象），直接送入协议层校验，不经过 `_render_markdown()` 渲染再被 Parser 解析回来。Parser 只处理手写的 `.step.md` 文件。

---

## 3. 重构的三大方向

### 方向一：全流程数据类型化（消灭文本往返）

**问题**：Generator 输出结构化对象后立即渲染成 Markdown 文本，Parser 再用正则解析回 dict，这是一次无意义的序列化往返，每次都有信息损失风险。`context` 是 `dict[str, Any]`，所有变量靠字符串 key 访问，类型边界完全隐式。

**目标**：整条数据流上每个"交接点"都有类型。

- `RunInput`：入口层 Pydantic 类型，验证初始参数
- `WorkflowBlueprint`：Planner 输出类型，直接存入 context，不序列化为 JSON 字符串
- `WorkflowModel`：Generator 直接输出，不经 Markdown 往返，直送协议层
- `ExecutionContext`：三层分离的类型化 context（`state: dict[str,Any]` / `meta: RunMeta` / `runtime: RuntimeState`）
- `StepModel`：Runner 主循环操作的步骤对象，Pydantic 类型
- `SkillInput` / `SkillOutput`：每个 Skill 声明的输入输出 Pydantic 类型，Runner 自动从 context 提取并写回

**影响**：`runtime_assertions.py` 的运行时前后置断言变成 Pydantic 在 Skill 入口的静态校验；`_parse_evaluator_report()` 等防御性解析方法消失；变量类型从调用时才崩溃变成边界处即时拦截。

**Parser 的定位调整**：保留，仅处理手写的 `.step.md` 文件（meta workflow 等）。LLM 生成物走 `StructuredWorkflowArtifact → WorkflowModel` 适配器路径，永远不经过 Parser。

### 方向二：角色 Prompt 写清楚规则（约束前置）

**问题**：Generator Prompt 没有 DSL 书写规则，靠 normalizer 事后打补丁；Evaluator 四维评分没有可执行的 rubric，LLM 自由裁量，轮次间分数不可比；每个 Skill 只注入技能名列表，LLM 不知道技能的用途、输入输出要求。

**目标**：LLM 生成时就遵守规则，而不是生成后靠代码修补。

- **Generator Prompt** 内嵌：DSL 字段命名规则（`**Input**` 单数）、变量名对齐约定（输出变量名必须与下游步骤 Input 声明一致）、`on_reject` 只能向前跳、至少两个完整的 few-shot 示例工作流（覆盖线性流和 on_reject 循环流）
- **Evaluator Prompt** 内嵌：四维权重明确（logic_closure 40% / safety_gate 30% / engineering_quality 20% / persona_adherence 10%）、每维最低分要求、强制 REJECTED 条件（static_scan 命中违规 → 直接 REJECTED，不进入语义评分）
- **SkillCard 体系**：每个 AgentSpec 声明 `name` / `description` / `when_to_use` / `do_not_use_when` / `input_schema` / `output_schema`，SkillRegistry 扫描时构建 `skill_manifest`，注入 Generator Prompt 替代纯名称列表
- **Prompt 外置**：system_prompt 和 few-shot 示例存入 `prompts/` 目录下的 `.md` 或 `.jinja2` 文件，带版本号，调参不动代码

### 方向三：技能元数据统一声明（消灭分散约束）

**问题**：action 合法性检查在 gatekeeper / security_scan / LLMGeneratorCall 三处各写一遍逻辑不同；技能幂等性和重试策略硬编码在 `error_policy.py` 的字典里，新增技能要同时修改多处；`_normalize_name()` 函数在 gatekeeper 和 dry_run 里各复制一份。

**目标**：每个 Skill 是自描述的，新增一个 Skill 只需要一个文件。

```python
# 每个 AgentSpec 类声明自己的全部元数据
class GeneratorSpec(LLMAgentSpec):
    name = "llm_generator_call"
    description = "基于 WorkflowBlueprint 生成可执行的 WorkflowModel"
    when_to_use = "接到 Planner 蓝图后，生成或修复工作流"
    
    input_type = GeneratorInput      # workflow_blueprint, prev_defects, escalation_level
    output_type = WorkflowModel      # 直接是 WorkflowModel，不经文本往返
    
    idempotency = IdempotencyLevel.L0
    retry_policy = RetryPolicy(max_retries=2, backoff=2.0)
    
    system_prompt_path = "prompts/generator_system_v1.md"
    user_prompt_template = GENERATOR_PROMPT_TEMPLATE
```

`error_policy.py` 从硬编码字典变成查 AgentSpec 注册表的工具函数；`security_scan.py` 的 action 白名单扫描合并到 Gatekeeper，不再重复；`_normalize_name()` 提取到 `protocol/utils.py`，协议层内部共用。

---

## 4. 分层架构设计

系统分为八层，依赖方向严格单向向下。

### 层 ①：入口与配置层

**负责什么**：CLI 参数解析、环境变量统一加载、Runner 实例组装、执行启动。这一层是系统的"外皮"，不承载任何业务逻辑或执行逻辑。

**为什么单独做一层**：当前 `main.py` 硬编码工作流路径和初始 context，无法独立测试入口层，也无法在不改代码的情况下切换启动方式（CLI / API / 测试）。`config/settings.py` 的引入使所有环境变量、阈值、常量有唯一来源，消灭散落在四个文件里的默认参数。

**直接数据交流的层**：→ 协调层（组装 Runner 并传入参数）

---

### 层 ②：协调层（Runner + 拆出的子模块）

**负责什么**：驱动步骤循环的薄编排器。读取步骤列表 → 调用 `ConditionEvaluator` → 调用 `StepExecutor` → 处理结果 → 更新 `ExecutionContext` → 循环。暴露 `ExecutionHooks` 接口供业务层注入行为（champion 更新、注册触发等），Runner 本体不知道任何业务内容。

**为什么单独做一层**：Runner 当前是 691 行的上帝类，同时承担循环编排、Champion 业务逻辑、工作流注册回放、context 压力观测等互不相关的职责。拆分后 Runner 目标 ≤ 150 行，每个子模块独立可测试。

子模块职责：

- `step_executor.py`：单步执行（skill 查找 + execute_with_policy + 输出写回 context）
- `condition_evaluator.py`：simpleeval 沙盒条件求值，独立可测试
- `resume_strategy.py`：断点续传（load state → hydrate context → 确定 start_step_id）
- `execution_hooks.py`：Hook 接口定义（on_step_start / on_step_end / on_workflow_complete）
- `execution_observer.py`：context 压力采样 + telemetry，与执行逻辑解耦

**直接数据交流的层**：← 入口层（接收 Runner 配置）；→ 协议层（提交 WorkflowModel 做校验）；→ 能力层（调用 Skill 执行）；→ 基础设施层（读写 StateStore、SkillRegistry）；↔ 业务编排层（通过 Hook 交互）

---

### 层 ③：协议层

**负责什么**：所有确定性规则的唯一来源。只消费 `WorkflowModel`（Pydantic 对象），零业务依赖，零 LLM 调用。

规则清单（完整，不重复，不分散）：

- `models.py`：`WorkflowModel / StepModel / WorkflowMetadata`，内部唯一真理
- `gatekeeper.py`：action ∈ registered_skills / on_reject < current_id / outputs 非空 / 无重复 step_id / 无复数 IO 标题——**唯一**实现处，security_scan 的 action 白名单扫描合并到这里
- `dry_run.py`：变量依赖图模拟执行，检测未解析变量和步骤可达性
- `security_scan.py`：危险关键词扫描 / [DANGER] [CONFIRM] 标记检查——保留，但不再重复做 action 检查
- `runtime_assertions.py`：执行前后对 StepModel 的 inputs/outputs 做契约断言
- `normalizer.py`：归一化和 legacy DSL 兼容处理
- `service.py`：统一入口 ProtocolService，编排 parse → schema → gatekeeper → dry_run
- `report.py` / `errors.py` / `error_codes.py`：统一错误结构

**为什么单独做一层**：V4 已建立这一层，方向正确。重构的工作是消灭层内重复（`_normalize_name()` 复制、action 检查三处）、让协议层错误能回流给 Generator（当前只打日志）。

**直接数据交流的层**：← 协调层（提交 WorkflowModel）；← 基础设施层（WorkflowRegistry 在注册前调用）；→ 业务编排层（ProtocolReport 错误反馈给 ChampionTracker）

---

### 层 ④：能力层（AgentSpec + Skills）

**负责什么**：每个 Skill 是自描述的执行单元，声明自己的 Prompt 模板、输入输出类型、幂等性、重试策略、SkillCard 元数据。LLM 技能（llm/）、I/O 技能（io/）、流程控制技能（flow/）按类型分子目录。`base.py` 定义抽象基类 `Skill[InputT, OutputT]` 和 `AgentSpec`。

**为什么单独做一层**：当前 `skills/atomic/` 是扁平目录，LLM 调用 skill 和文件 I/O skill 混放，`error_policy.py` 的策略与技能定义分离（新增技能需改两处）。重构后 AgentSpec 把 Prompt + 类型 + 元数据集中在一处，SkillRegistry 递归扫描，新增技能只需一个文件。

**直接数据交流的层**：← 协调层（被 StepExecutor 调用）；→ 基础设施层（LLM 技能通过 LLMClientRegistry 调用模型）；← 协议层（AgentSpec 的 input_type/output_type 是协议层 Pydantic 类型的子集）

---

### 层 ⑤：业务编排层

**负责什么**：Meta Workflow 专属的业务逻辑，通过 ExecutionHooks 接入 Runner，引擎本体不知道这些逻辑存在。

核心模块：

- `champion_tracker.py`：Champion 竞选逻辑（当前 Runner 里的 8 个方法）——requirement_fingerprint / blueprint_fingerprint / champion 更新 / handoff_artifact 构建

**为什么单独做一层**：Champion 机制是 Meta Workflow 的业务规则，不是引擎的通用能力。当前通过 `workflow_name == "Meta Main Workflow"` 字符串判断激活，这是业务逻辑硬编码在引擎里的最典型反例。独立后，普通工作流运行时这些逻辑完全不存在，Meta Workflow 启动时才注入。

**直接数据交流的层**：← 协调层（通过 Hook 接收 step 执行结果）；→ 基础设施层（StateStore 读写 champion_json / run_meta）；← 协议层（接收 ProtocolReport 用于注册决策）

---

### 层 ⑥：基础设施层

**负责什么**：所有外部依赖的适配器，可替换，不承载业务逻辑。

模块清单：

- `state_store.py`：实现 `AbstractStateStore` 接口，默认 SQLite 实现，未来可换 Redis/Postgres
- `llm_factory.py` / `llm_client_registry.py`：LLM 客户端单例化，按 (provider, model, temperature) 为 key 缓存，复用 httpx 连接池
- `workflow_registry.py`：注册索引管理，只写已通过协议层的 WorkflowModel
- `context_manager.py`：token 压力估算工具，soft reset（裁剪 chat_history 保留摘要）/ hard reset（触发 handoff artifact → 新 Runner 恢复）
- `variable_mapper.py`：父子工作流变量映射，不被 skill 直接 import，通过 StepExecutor 调用
- `error_policy.py`：从硬编码字典改为查 AgentSpec 注册表的工具函数

**为什么单独做一层**：当前 `llm_factory.py` 混在 `engine/` 里，导致 skill → engine 的反向依赖，形成隐式循环依赖。统一到 `infra/` 后依赖方向变为 `skills/ → infra/`，干净切断。

**直接数据交流的层**：← 协调层 / 业务编排层 / 能力层（被这些层调用）；→ 外部（LLM API、SQLite 文件系统）

---

### 层 ⑦：工作流资源层

**负责什么**：`.step.md` 文件和注册索引，是数据而不是代码。`.step.md` 只做编排声明，不承载任何规则、Prompt 或幂等性配置。

目录结构：

- `workflows/meta/`：系统内置的元工作流（Planner、Designer、Evaluator、Main）
- `workflows/dev/`：LLM 生成的工作流产物
- `workflows/registry/`：`index.json` 独立存放，与工作流文件生命周期解耦
- `workflows/templates/`：few-shot 示例工作流，被 Generator Prompt 引用

**为什么单独做一层**：工作流文件是运行时数据，不是代码模块。`index.json` 当前和工作流文件放在同一目录，注册索引和内容文件绑定在一起，独立后可以支持多索引、备份、迁移。

**直接数据交流的层**：← 协调层（Parser 读取 .step.md）；← 基础设施层（WorkflowRegistry 写入 dev/ 和 registry/）；← 能力层（Generator Prompt 引用 templates/）

---

### 层 ⑧：测试层

**负责什么**：按测试范围分四类，各自独立，不共用 fixture。

- `tests/unit/`：单模块测试，mock 所有外部依赖
- `tests/integration/`：多模块联动测试，含协议层 gate 测试
- `tests/e2e/`：真实 LLM 调用的端到端测试，有网络隔离标记
- `tests/fixtures/`：测试用 .step.md 样本统一管理，不再散落各测试文件

**直接数据交流的层**：← 所有层（测试覆盖所有层）

---

## 5. 项目目录结构

```
myworkflow/
├── main.py                                # 入口：组装并启动 Runner
├── cli.py                                 # CLI：run / replay / list 命令
│
├── config/
│   └── settings.py                        # 所有环境变量、阈值、常量的唯一来源
│
├── prompts/                               # Prompt 模板文件（外置，带版本）
│   ├── planner_system_v1.md
│   ├── generator_system_v1.md             # 含 DSL 规则 + few-shot 示例
│   └── evaluator_system_v1.md             # 含四维 rubric + 强制 REJECTED 条件
│
├── agent/
│   ├── engine/
│   │   ├── runner.py                      # 薄编排器，目标 ≤ 150 行
│   │   ├── step_executor.py               # 单步执行（从 runner 拆出）
│   │   ├── condition_evaluator.py         # simpleeval 沙盒求值（从 runner 拆出）
│   │   ├── resume_strategy.py             # 断点续传策略（从 runner 拆出）
│   │   ├── execution_hooks.py             # Hook 接口定义
│   │   ├── execution_observer.py          # Telemetry 观测（从 runner 拆出）
│   │   └── parser.py                      # 仅处理手写 .step.md，LLM 生成物不经此
│   │
│   └── engine/protocol/
│       ├── models.py                      # WorkflowModel / StepModel（Pydantic 唯一真理）
│       ├── gatekeeper.py                  # 所有确定性硬规则的唯一实现处
│       ├── dry_run.py                     # 变量依赖图模拟执行
│       ├── security_scan.py               # 危险关键词扫描（不再重复做 action 检查）
│       ├── runtime_assertions.py          # 执行前后契约断言
│       ├── normalizer.py                  # 归一化与 legacy 兼容
│       ├── service.py                     # ProtocolService 统一入口
│       ├── report.py                      # 统一错误结构
│       ├── errors.py
│       ├── error_codes.py
│       └── utils.py                       # 新增：_normalize_name 等共用工具（消灭复制）
│
├── agent/skills/
│   ├── base.py                            # Skill 抽象基类 + AgentSpec（Prompt+类型+元数据）
│   ├── llm/
│   │   ├── planner.py                     # PlannerSpec（含 system_prompt_path + 类型 + 重试）
│   │   ├── generator.py                   # GeneratorSpec（直出 WorkflowModel，不经文本往返）
│   │   ├── evaluator.py                   # EvaluatorSpec（含四维 rubric 引用）
│   │   └── prompt.py                      # 通用 LLM 调用（llm_prompt_call）
│   ├── io/
│   │   ├── file_reader.py
│   │   └── file_writer.py
│   └── flow/
│       └── sub_workflow_call.py           # 不再直接 import VariableMapper
│
├── agent/orchestration/
│   └── champion_tracker.py                # Champion 竞选逻辑（从 runner 拆出的 8 个方法）
│
├── agent/infra/
│   ├── state_store.py                     # AbstractStateStore 接口 + SQLite 实现
│   ├── llm_client_registry.py             # LLM 客户端单例化，复用 httpx 连接池
│   ├── llm_factory.py                     # build_chat_model 工厂（从 engine/ 移来）
│   ├── workflow_registry.py               # 注册索引管理
│   ├── context_manager.py                 # 压力估算 + soft/hard reset 真正闭环
│   ├── variable_mapper.py                 # 父子工作流变量映射
│   └── error_policy.py                    # 查 AgentSpec 注册表的工具函数（不再硬编码字典）
│
├── workflows/
│   ├── meta/                              # 系统内置元工作流
│   │   ├── main_workflow.step.md
│   │   ├── workflow_planner.step.md
│   │   ├── workflow_designer.step.md
│   │   └── quality_evaluator.step.md
│   ├── dev/                               # LLM 生成的工作流产物
│   ├── registry/                          # index.json 独立存放
│   │   └── index.json
│   └── templates/                         # few-shot 示例，被 Generator Prompt 引用
│       ├── example_linear.step.md
│       └── example_with_on_reject.step.md
│
└── tests/
    ├── unit/
    ├── integration/
    ├── e2e/                               # 真实 LLM 调用，有网络隔离标记
    └── fixtures/                          # 测试用 .step.md 样本统一管理
```

---

## 6. 业务流程链路图

系统有两条主要业务流程：**生成工作流**（Meta Workflow 主链路）和**调用工作流**（已注册工作流的执行链路）。

### 6.1 生成工作流链路（Meta Workflow）

```
用户输入 requirement: str
    │
    ▼
[ 入口层 ] cli.py / main.py
  RunInput(requirement=...) 组装
    │
    ▼
[ 协调层 ] Runner.run()
  加载 meta/main_workflow.step.md（Parser 解析）
  注入 ExecutionHooks（ChampionTracker）
    │
    ├── Step 1: sub_workflow_call → workflow_planner.step.md
    │     [ 能力层 ] PlannerSpec.execute()
    │       LLM 调用（结构化输出）
    │       ─────────────────────────────────────
    │       输出：WorkflowBlueprint（Pydantic）
    │       写入 ExecutionContext.state["workflow_blueprint"]
    │
    ├── Step 2: sub_workflow_call → workflow_designer.step.md
    │   （条件：not prev_defects / prev_defects）
    │     [ 能力层 ] GeneratorSpec.execute()
    │       读取 WorkflowBlueprint + skill_manifest（来自 SkillRegistry）
    │       LLM 调用（Pydantic 结构化输出）
    │       ─────────────────────────────────────
    │       输出：WorkflowModel（Pydantic，不经 Markdown 往返）
    │       写入 ExecutionContext.state["final_artifact"]
    │
    ├── Step 3: sub_workflow_call → quality_evaluator.step.md
    │     [ 能力层 ] EvaluatorSpec.execute()
    │       静态安全扫描（SecurityScan）→ 命中则直接 REJECTED
    │       LLM 语义评审（四维 rubric）
    │       ─────────────────────────────────────
    │       输出：EvaluatorReport（Pydantic）
    │       写入 ExecutionContext.state["evaluator_report"]
    │
    │   [ 协调层 ] Runner 读取 on_reject 路由：
    │   ┌── REJECTED → 更新 prev_defects + escalation_level
    │   │              清空 chat_history（Context Reset）
    │   │              跳回 Step 2（最多 4 轮，第 4 轮触发 L4 人工阻断）
    │   └── APPROVED → 继续
    │
    │   [ 业务编排层 ] ChampionTracker（通过 on_workflow_complete Hook 触发）
    │     更新 champion_json（score 比较）
    │     构建 handoff_artifact
    │
    ├── 注册流程（ExecutionHooks.on_workflow_complete）
    │   [ 协议层 ] ProtocolService
    │     Gatekeeper（action 合法性、变量可达、on_reject 完整性）
    │       │ 失败 → ProtocolReport errors 回流给 Generator（下一轮 prev_defects 合并）
    │     DryRun（变量依赖图模拟执行）
    │       │ 失败 → 同上
    │     通过 → 继续
    │   [ 基础设施层 ] WorkflowRegistry
    │     WorkflowModel 写入 dev/
    │     index.json 写入 registry/
    │   [ 协调层 ] Runner 自动回放（验证可执行性）
    │
    ▼
输出：workflow_id + WorkflowModel 持久化完成
```

---

### 6.2 调用工作流链路（已注册工作流执行）

```
用户输入 workflow_id + inputs: dict
    │
    ▼
[ 入口层 ] cli.py
  WorkflowRegistry.resolve_path(workflow_id) → .step.md 文件路径
  RunInput(filepath=..., context=inputs) 组装
    │
    ▼
[ 基础设施层 ] StateStore.connect()
  检查 run_id 是否有历史状态（断点续传）
    │
    ├── 有历史 → ResumeStrategy.hydrate(run_id)
    │           恢复 ExecutionContext（state + meta + runtime）
    │           确定 start_step_id
    └── 无历史 → 全新执行，start_step_id = 1
    │
    ▼
[ 协调层 ] Runner 主循环
  Parser 解析 .step.md → WorkflowModel（手写文件走 Parser）
    │
    ├── 每步执行前：
    │   ConditionEvaluator.eval(condition, context) → bool（跳过 or 继续）
    │   ExecutionObserver.on_step_start(step_id)（context 压力采样）
    │   RuntimeAssertions.validate_inputs(step, context)（前置断言）
    │
    ├── 执行：
    │   [ 能力层 ] StepExecutor.execute(step, context)
    │     SkillRegistry.get(skill_name) → AgentSpec 实例
    │     execute_with_policy(skill, input_model)（幂等性 + 重试）
    │     ─────────────────────────────────────
    │     输出：SkillOutput（Pydantic）
    │     写回 ExecutionContext.state
    │
    ├── 每步执行后：
    │   RuntimeAssertions.validate_outputs(step, output, context)（后置断言）
    │   ExecutionObserver.on_step_end(step_id)
    │   StateStore.save_step_state(run_id, step_id, "success", output, context)
    │
    ├── 失败处理：
    │   SkillNotFoundError → 硬失败，进入 ErrorPolicy，不软跳过
    │   RetryableError → execute_with_policy 按 AgentSpec.retry_policy 重试
    │   ExhaustedError → StateStore 记录 failed，抛出等待人工干预
    │
    └── 全部步骤完成：
        ExecutionObserver.flush_stats(run_id)
        StateStore.save_run_state(run_id, "completed", ...)
    │
    ▼
输出：RunResult(run_id, status="success", context)
```

---

## 7. LLM 权力边界与幻觉控制

### 7.1 权力边界三条铁律

**LLM 可以做的**：生成 WorkflowModel 的内容字段（步骤名称、描述、输入输出声明）；给出语义性质量评审（四维打分、缺陷描述、修复建议）；根据 SkillCard 描述选择合适的技能名称。

**LLM 不可以做的**：

1. 决定流程跳转——路由权在 Runner（`on_reject` 由开发者在 `.step.md` 声明）
2. 使用不在 SkillRegistry 白名单里的技能名——物理层面由 Pydantic `Literal[...]` 枚举阻止
3. 绕过协议层——Evaluator APPROVED ≠ 可注册，注册前必须过 Gatekeeper + DryRun
4. 影响引擎运行参数——Generator 输出的 WorkflowModel 只包含内容字段，引擎行为参数不暴露给 LLM

### 7.2 五层幻觉防御体系

| 层次 | 手段 | 防御的问题 |
|------|------|-----------|
| 第一层 | Pydantic `Literal[skill_names...]` 枚举约束 action 字段 | LLM 物理上无法生成不在白名单的技能名 |
| 第二层 | Generator Prompt 内嵌 SkillCard（名称+用途+输入输出） | LLM 知道技能能做什么，不会误用 |
| 第三层 | Generator Prompt 内嵌 few-shot 示例工作流 | LLM 模仿正确格式，减少 DSL 格式幻觉 |
| 第四层 | Gatekeeper + DryRun 拦截不合规产物，错误回流 Generator | 生成后立即校验，错误原因反馈触发修复循环 |
| 第五层 | RuntimeAssertions 前后置断言 | 运行时最后防线，发现 LLM 引用了根本不可达的变量 |

### 7.3 SkillCard 注入格式

Generator Prompt 接收的技能描述从纯名称列表升级为：

```
### file_reader
用途：读取本地文件内容，返回文本字符串
何时使用：需要读取文件、配置、模板等本地资源时
不要用于：写入、修改或删除文件（使用 file_writer）
输入：file_path: str（必填）
输出：file_content: str；error: str（可选，读取失败时）

### sub_workflow_call
用途：调用另一个已注册的子工作流，传递变量并接收结果
特殊字段：需要声明 **Workflow**: <path> 字段指定子工作流路径
输入：由子工作流 frontmatter inputs 决定
输出：由子工作流 frontmatter outputs 决定
```

---

## 8. 约束规则的归属原则

### 8.1 判断标准

一条规则应该放在哪里，只有一个判断标准：**这条规则是"可由代码直接判定对错"的，还是"需要理解语义才能判断"的**？

- **确定性规则** → 必须在 `protocol/` 层用代码实现，同时也要写进 Prompt（让 LLM 遵守，代码是最终防线）
- **语义性约束** → 只能在 Prompt 层，代码无法判断

### 8.2 归属分类表

| 规则 | 归属 | 理由 |
|------|------|------|
| action 必须在白名单 | 代码（Gatekeeper）+ Prompt | 确定性，代码可直接判定 |
| on_reject 目标必须 < 当前步骤号 | 代码（Gatekeeper）+ Prompt | 确定性，整数比较 |
| outputs 不能为空 | 代码（Gatekeeper）| 确定性 |
| 变量依赖必须可达 | 代码（DryRun）| 确定性，DAG 模拟 |
| 危险关键词必须标 [DANGER] | 代码（SecurityScan）+ Prompt | 确定性，正则匹配 |
| 步骤逻辑是否闭合 | Prompt（Evaluator）| 语义性，需理解意图 |
| 流程描述是否清晰 | Prompt（Evaluator）| 语义性 |
| 架构拆分是否合理 | Prompt（Planner）| 语义性 |
| 四维评分权重和阈值 | Prompt（Evaluator）| 评分策略 |
| DSL 字段命名规范 | 代码（Normalizer/Gatekeeper）+ Prompt | 两层，代码修复容错，Prompt 预防 |

### 8.3 `.step.md` 与 `AgentSpec` 的职责边界

**`.step.md` 只做编排声明**：步骤顺序、Action 名称（对应 AgentSpec key）、Input/Output 变量名、on_reject 路由、condition 表达式。不承载任何 Prompt 内容、幂等性声明、校验逻辑。

**`AgentSpec` 集中角色全部属性**：Prompt 模板（路径引用）、输入输出 Pydantic 类型、幂等性等级、重试策略、SkillCard 元数据。维护一个角色只需要改一个文件。

**`protocol/`** 只消费 `WorkflowModel`，对角色和工作流内容无感知。

---

## 9. 其他优化事项与优先级

### P0（与三大方向同步，必须同步落地）

- **SkillCard 元数据体系**：AgentSpec 声明 description / when_to_use / input_schema / output_schema，SkillRegistry 构建 skill_manifest 注入 Generator Prompt——消灭技能幻觉的根本解
- **协议层错误回流**：Gatekeeper / DryRun 失败的 ProtocolReport errors 合并进 prev_defects，Generator 修复时能看到协议层拒绝原因
- **Pydantic Literal 枚举 action 字段**：Generator 的 WorkflowStepSpec.action 从 str 改为动态构建的 Literal 枚举，物理层面阻止幻觉技能名
- **ContextManager 真正闭环**：soft reset → 裁剪 chat_history 保留摘要；hard reset → 触发 handoff artifact → 新 Runner 恢复（当前 Harness Layer 1 只观测不行动）
- **protocol/utils.py**：提取 `_normalize_name()` 等重复函数，消灭协议层内部复制

### P1（结构清晰度，尽早完成避免后期改动代价高）

- **LLM 客户端单例化**：LLMClientRegistry 按 (provider, model, temperature) 缓存客户端，复用 httpx 连接池
- **Prompt 外置为模板文件**：system_prompt 迁移到 `prompts/` 目录，调参不动代码，天然版本历史
- **Evaluator Rubric 显式化**：四维权重、分数阈值、强制 REJECTED 条件写入 Prompt 文件
- **AbstractStateStore 接口**：5 个方法抽象接口，SQLiteStateStore 是默认实现，未来换后端不改调用方
- **few-shot 模板工作流**：`workflows/templates/` 放 2-3 个标准示例，Generator system_prompt 引用

### P2（好的工程实践，有空做）

- **ExecutionObserver 协议**：定义 Observer 接口，context_pressure 采样、step 耗时都走 Observer，未来可换 OpenTelemetry
- **config/settings.py 统一**：用 pydantic-settings 做类型化的配置中心
- **ResumeStrategy 独立**：支持全量恢复 / 步骤级恢复 / 不恢复（测试用）三种策略

### 暂不做

- **动态生成技能**：LLM 生成 Python 代码动态加载执行。安全沙箱难做，无法通过协议层校验。正确方向是把已有技能做成可配置的（llm_prompt_call 支持 system_prompt 参数注入），不需要动态生成
- **完整 FastAPI server**：预留 `api/` 目录和 `server.py` 框架，不实装 endpoint
- **多 Agent 并行执行**：当前是严格顺序执行，并发在主循环里无意义，等步骤间 DAG 依赖明确后再考虑

---

## 10. 协议冻结与变更治理

继承 V4 建立的治理机制，在重构期间同样适用。

### 10.1 协议变更登记规则

任何涉及以下内容的变更，必须先登记再合入：

- `protocol/models.py` 的 Schema 字段变更
- `protocol/gatekeeper.py` 的硬规则新增或修改
- `protocol/dry_run.py` 的执行契约逻辑变更
- Generator Prompt 的结构化输出契约变更
- Evaluator Prompt 的评分规则或强制 REJECTED 条件变更

### 10.2 重构期间的 Gate 测试

每个重构阶段完成后必须通过：

```bash
# 协议层 gate（必跑）
uv run pytest tests/integration/test_m3_closure_gates.py -q
uv run pytest tests/integration/test_dsl_cutover_gates.py -q

# 邻近回归（必跑）
uv run pytest tests/integration/ -q

# 全量回归（合入前必跑，连续两轮通过）
uv run pytest -q
```

### 10.3 重构实施顺序建议

按收益/风险比从高到低，每步独立可回归：

1. `config/settings.py` + `protocol/utils.py`（风险最低，1 天）
2. `infra/` 层整合（只改 import 路径，不改逻辑，2 天）
3. `skills/` 按类型重组 + SkillCard 声明（SkillRegistry 递归扫描改一行，3 天）
4. Runner 拆分（`step_executor` / `condition_evaluator` / `execution_hooks`，需单测护航，5 天）
5. `ChampionTracker` 独立（配合 ExecutionHooks，3 天）
6. Generator 结构化路径打通（方向一核心，消灭文本往返，5 天）
7. Generator Prompt + Evaluator Prompt 强化（方向二，3 天）
8. ContextManager 真正闭环（soft/hard reset，3 天）
