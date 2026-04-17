# MyWorkflow 设计档案 · 02 · 协议层与 DSL

> 读前置:00 · 顶层概览、01 · 架构与目录
> 本文档目标:把 MyWorkflow 最具创新性的两件事——**`.step.md` DSL** 和 **协议层(`protocol/`)**——讲清楚到能被复现的程度。
> 这份文档是整个设计档案的核心。

---

## 1. 为什么需要协议层

主流 Agent 框架的一个普遍缺陷是:**"规则散在 Prompt 里"**。

具体表现:
- "Action 必须在白名单里" → 写在 LLM Prompt 里,LLM 偶尔会幻觉一个不存在的 action 名
- "on_reject 必须指向更早的步骤" → 没有人检查,LLM 可能输出 `on_reject: 999`
- "变量必须在被引用前定义" → LLM 可能引用一个根本没人产出的变量
- "危险关键词必须有 `[DANGER]` 标记" → 完全靠人类纪律

这些规则的共同特征是:**它们都可以由代码用 30 行内的逻辑直接判定对错**。把它们交给 LLM 是浪费 LLM、又不可靠。

**协议层 = 把所有"可由代码确定地判定对错"的规则集中到一个独立的子系统,作为最终判官。**

设计哲学:

> 能用代码判定的规则,代码做最终判官,Prompt 做预防教育;能让 LLM 判定的,Prompt 给 rubric,代码不掺和。

---

## 2. 协议层的边界(零依赖原则)

```
协议层 ✕ 不依赖 业务编排层
协议层 ✕ 不依赖 协调层(Runner)
协议层 ✕ 不依赖 LLM(零网络调用)
协议层 ✕ 不依赖 IO(除了 service.py 读取 .step.md 文件这一处)
协议层 ✓ 依赖 Pydantic(类型基础)
协议层 ✓ 依赖 标准库
```

**这个边界保证协议层是"纯函数式的逻辑包",可以被任何上游模块安全地调用,不会引入隐式耦合,也极易被 unit 测试(构造一个 WorkflowModel 即可,无需 mock 任何东西)。**

---

## 3. 协议层模块清单与详细职责

### 3.1 `models.py` — 系统的"内部真理"

定义三个核心 Pydantic 类:

```python
class WorkflowMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = "UNKNOWN"
    description: Optional[str] = None
    version: Optional[str] = None
    inputs: list[str] | dict[str, str] = Field(default_factory=list)
    outputs: list[str] | dict[str, str] = Field(default_factory=list)

class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    name: str = ""
    content: str = ""
    action: str
    workflow: Optional[str] = None       # sub_workflow_call 时的子流程路径
    condition: Optional[str] = None      # simpleeval 表达式
    on_reject: Optional[int] = None      # 必须 > 0 的目标 step_id
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)

class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    metadata: WorkflowMetadata = Field(default_factory=WorkflowMetadata)
    steps: list[WorkflowStep] = Field(default_factory=list)
```

**关键设计:**

- **`extra="allow"`**:允许 frontmatter 携带未来可能的新字段,迁移期不破坏;严格规则交给 gatekeeper 专门检查(不是 Pydantic 默认的"未知字段拒绝")。

- **`field_validator(mode="before")` 大量使用**:在 Pydantic 解析前做归一化。例如 `_normalize_action` 把 `None` / 空串归一为 `"unknown"`,让下游有稳定的字符串可比;`_normalize_on_reject` 把字符串 `"3"` 转 int,负值或 0 转 None。

- **`model_validator(mode="before")` 兜底**:`WorkflowModel._ensure_shape` 保证传入 None 或缺字段时也能构造一个空的合法对象,避免 ValidationError 在意外位置爆出。

**这套设计的本质:** Pydantic 不仅是类型校验器,更是"不确定输入 → 确定结构"的归一化器。归一化在 Pydantic 内部完成,gatekeeper 拿到的就是干净对象,逻辑可以专注做规则判断。

---

### 3.2 `gatekeeper.py` — 硬规则的唯一实现处

`validate_workflow(workflow: WorkflowModel, registered_skills) -> ProtocolReport`

**检查的硬规则(一个不漏):**

| 错误码 | 规则 |
|--------|------|
| `WF_EMPTY_STEPS` | 工作流必须至少一个 step |
| `STEP_DUPLICATE_ID` | step.id 不能重复 |
| `STEP_INVALID_IO_HEADER` | 内容里不能出现 `**Inputs**:` `**Outputs**:` (复数标题) |
| `STEP_ON_REJECT_TARGET_MISSING` | on_reject 目标 step_id 必须存在 |
| `STEP_ON_REJECT_NOT_BACKWARD` | on_reject 目标必须 < 当前 step_id(只能向前跳)|
| `STEP_INVALID_ACTION` | action 不能是空或 "unknown" |
| `STEP_MISSING_OUTPUT` | 至少声明一个 output 变量 |
| `STEP_INPUT_TEMPLATE_RESIDUE` | inputs 不能残留 `{{...}}` 模板语法 |
| `STEP_INPUT_UNBOUND` | input 引用的变量必须在前面步骤已 produce(或 metadata.inputs 已声明)|
| `STEP_OUTPUT_TEMPLATE_RESIDUE` | output 名不能含模板语法 |
| `WF_UNKNOWN_ACTIONS` | action 必须在 registered_skills 白名单里 |

**重要细节:可达性是"前向滚雪球"算法。** 实现上维护一个 `available_vars: set[str]`,从 `metadata.inputs + infer_minimal_inputs(workflow)` 出发,逐步扫每个 step,把 `step.outputs.keys()` 加进 set,再校验下一个 step 的 inputs 是否都在 set 里。这个算法 O(N) 时间、O(V) 空间,既精确又高效。

**输入变量"可选标记"约定:** 用户在 input 名字结尾加 `?` 表示该输入可选(`existing_data?`),gatekeeper 跳过 unbound 检查。这是给 sub_workflow_call 等场景留的口子。

---

### 3.3 `dry_run.py` — 变量依赖图模拟执行

`dry_run_contract_check(workflow, available_context) -> DryRunResult`

不真正执行 Skill,而是**模拟"如果按声明执行会发生什么"**:

```python
class DryRunStepTrace(BaseModel):
    step_id: int
    action: str
    executed: bool
    missing_inputs: list[str]
    declared_outputs: list[str]
    produced_outputs: list[str]

class DryRunContractReport(BaseModel):
    all_steps_executed: bool
    step_io_assertions_passed: bool
    no_undefined_variables: bool
    no_suppressed_errors: bool
    unresolved_variables: list[str]
    traces: list[DryRunStepTrace]

class DryRunResult(BaseModel):
    status: Literal["passed", "failed", "skipped"]
    required_inputs: list[str]
    missing_inputs: list[str]
    report: ProtocolReport
    contract_report: DryRunContractReport
```

**dry_run 与 gatekeeper 的关系:** gatekeeper 是"静态结构检查"(不需要 context),dry_run 是"模拟执行检查"(需要知道初始 context 有哪些键)。dry_run 能发现 gatekeeper 发现不了的:
- 工作流本身合法,但当前 context 缺关键 input
- 某个 step 的 condition 永远求值为 false → 后面的 step 不可达
- 变量名打错(`fileconent` vs `file_content`)在某个调用时才暴露

---

### 3.4 `security_scan.py` — 静态安全审计

```python
DANGER_KEYWORDS = [
    r"\brm\b", r"\brmdir\b", r"shutil\.rmtree",
    r"DROP\s+TABLE", r"DELETE\s+FROM",
    r"git\s+push", r"git\s+reset\s+--hard",
    r"\bsubprocess\b", r"os\.system",
    r"\bshutdown\b", r"\breboot\b",
]

CONFIRM_KEYWORDS = [
    r"\bfile_writer\b", r"\bgit_commit\b",
    r"http\s+POST", r"http\s+PUT", r"http\s+PATCH",
    r"\bdeploy\b", r"\bpublish\b", r"\bsend_email\b",
]
```

**两类规则:**

- **DANGER**:命中关键词 → 必须有 `[DANGER]` 标记,否则 `violations`(blocker,直接 REJECTED)
- **CONFIRM**:命中关键词 → 必须有 `[CONFIRM]` 或 `[DANGER]` 标记,否则 `warnings`(non-blocker,但记录)

**算法:** 关键词 + 上下文窗口(前后 2 行)内必须出现标记。这个窗口设计避免了"标记和命令距离太远"的钻空子。

**为什么是正则不是 AST:** `.step.md` 是 Markdown 不是代码,不需要 AST 也无法准确 AST(嵌入的代码块语言可能不一致)。正则在这个场景准确度足够,且实现简单可审计。

---

### 3.5 `runtime_assertions.py` — 运行时契约断言

执行前后由 Runner 调用,作为"运行时最后防线":

```python
def validate_step_inputs(step: dict, context: dict) -> None
def validate_step_outputs(step: dict, output: dict, context: dict) -> None
```

**为什么需要它**(已经有 gatekeeper 和 dry_run):
- gatekeeper 是注册前的静态检查,但**手写**的 meta 工作流跳过 gatekeeper 直接被 Runner 执行
- 实际运行时 context 可能被中途破坏(虽然系统设计上不允许,但作为最后兜底)
- LLM 输出的 output 可能缺声明的字段,前置假设需要保证

它是冗余的——但这种冗余正是工程纪律的体现:**不依赖任何上游正确性,在自己能检查的边界一定要检查**。

---

### 3.6 `normalizer.py` — 归一化与 legacy 兼容

`normalize_parsed_data(parsed) -> dict` 在 Parser 输出和 WorkflowModel 构造之间做一次清洗:
- `**Inputs**` → `**Input**`(单数化)
- frontmatter 里 legacy 的 `on_reject` 字段标记 `_legacy_on_reject_used=True`(供 service 输出 deprecation warning)
- 其他历史遗留字段名映射

**这一层的存在意义:** DSL 在演进,旧文件不应该被强制改写。Normalizer 是"兼容层",让协议层下游永远看到统一格式。

---

### 3.7 `service.py` — 协议层统一入口

`ProtocolService` 是协议层暴露给外界的**唯一**门面。所有上游(Runner / WorkflowRegistry / Evaluator)都只调用它,不直接 import 协议层内部模块。

**核心 API:**

```python
class ProtocolService:
    def parse_workflow_file(filepath) -> tuple[WorkflowModel, dict]
    def parse_parsed_data(parsed_data) -> tuple[WorkflowModel, dict]
    
    def validate(workflow, registered_skills, raise_on_error) -> ProtocolReport
    def dry_run(workflow, available_context, raise_on_error) -> DryRunResult
    
    def pre_register_check(workflow, ...) -> tuple[ProtocolReport, DryRunResult]
    def evaluate_workflow_file(filepath, ...) -> dict   # 一次性跑完所有检查
    
    def validate_runtime_step_inputs(step, context) -> None
    def validate_runtime_step_outputs(step, output, context) -> None
    
    def issue_code_catalog() -> dict   # 错误码清单(版本化)
    def infer_required_inputs(workflow) -> list[str]
```

**`evaluate_workflow_file` 是注册前的一站式检查**:Parser → SecurityScan → Gatekeeper → (可选) DryRun,合并到一个 ProtocolReport,返回 `{"valid": bool, "summary": str, "protocol_report": dict, "dry_run": dict}`。

---

### 3.8 `report.py` 与 `error_codes.py` — 统一错误结构

```python
class ProtocolReport(BaseModel):
    passed: bool
    errors: list[ProtocolIssue]
    warnings: list[ProtocolIssue]
    
    def add_error(code, message, location, suggestion) -> None
    def add_warning(code, message, location, suggestion) -> None
    def merge(other: ProtocolReport) -> None
    def has_errors() -> bool
    def summary() -> str
    def to_audit_dict() -> dict   # 审计输出
```

错误码常量集中在 `error_codes.py`,**版本化**(`PROTOCOL_ISSUE_CODE_CATALOG_VERSION`),变更必须经过协议变更登记(治理纪律)。

**为什么错误结构要统一:** 因为协议层的下游(Generator 修复循环、Evaluator 强制 REJECTED、CLI 输出)需要统一消费这些错误。如果每个检查器都自己定义错误格式,下游要写 N 套消费逻辑。统一结构后,**协议错误能被结构化地回流给 Generator,作为下一轮 prev_defects**(详见重构补充 1)。

---

## 4. `.step.md` DSL 完整规范

### 4.1 设计原则

`.step.md` = **YAML frontmatter + Markdown 正文 + 步骤块**。

为什么用 Markdown 不用 JSON/YAML/纯 Python:

| 选项 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| Markdown + frontmatter | 同时是文档/配置/可被 LLM 生成 | 需要 Parser | ✓ 选 |
| 纯 JSON | 易解析 | LLM 容易把代码字段名打错;非人类友好 | ✗ |
| 纯 YAML | 比 JSON 友好 | 缩进敏感,LLM 易出错 | ✗ |
| Python DSL | 强类型 | 动态执行有安全风险;LLM 生成代码品质波动大 | ✗ |

**核心选择:同一份 artifact 同时可以被人读、被 LLM 生成、被 Parser 解析,三个角色统一,大幅降低人机协同成本。**

### 4.2 文件结构

```markdown
---
name: 示例工作流
description: 这个工作流读一个文件并把内容写到另一个地方
version: 1.0
inputs:
  - source_path
  - target_path
outputs:
  - bytes_written
---

# 示例工作流

## Step 1: 读取源文件

**Action**: `file_reader`

**Input**:
- file_path: source_path

**Output**:
- file_content

读取 source_path 指定的文件,产出 file_content。

---

## Step 2: 写入目标文件

**Action**: `file_writer`

**Input**:
- target_path: target_path
- content: file_content

**Output**:
- bytes_written

将 file_content 写入 target_path,返回写入字节数。

---

## Step 3: 验证写入(Evaluator)

**Action**: `llm_evaluator_call`

**Input**:
- artifact: bytes_written

**Output**:
- evaluator_report

**on_reject**: 1

[CONFIRM] 验证写入成功,失败时回到 Step 1 重试。
```

### 4.3 字段语义(冻结清单)

#### Frontmatter(YAML)

| 字段 | 类型 | 必填 | 语义 |
|------|------|------|------|
| `name` | str | ✓ | 工作流唯一名称,Parser 会 normalize |
| `description` | str | ✗ | 一句话描述,无业务影响 |
| `version` | str | ✗ | 版本号字符串 |
| `inputs` | list[str] 或 dict[str,str] | ✗ | 工作流入参清单 |
| `outputs` | list[str] 或 dict[str,str] | ✗ | 工作流出参清单 |

#### 步骤块(Markdown)

每个 step 必须由 `## Step <id>: <name>` 开头。step 内必须包含的字段:

| 字段 | 必填 | 语义 | 校验规则 |
|------|------|------|---------|
| `**Action**: skill_name` | ✓ | 调用的技能名 | 必须在 registered_skills 白名单 |
| `**Input**: ...` | 视情况 | 输入变量映射 | 引用变量必须可达 |
| `**Output**: ...` | ✓ | 输出变量声明 | 至少 1 个;不能含模板语法 |
| `**Workflow**: path` | sub_workflow_call 时 ✓ | 子流程路径 | 文件必须存在 |
| `**condition**: expr` | ✗ | simpleeval 条件表达式 | 失败时跳过当前 step |
| `**on_reject**: <step_id>` | ✗ | REJECTED 时跳转目标 | 必须 < 当前 step_id |
| 正文文本 | ✗ | 描述,会被注入到 LLM Skill 的 prompt | 危险关键词需 `[DANGER]` 标记 |

#### 关键禁律

- 禁止使用 `**Inputs**:` `**Outputs**:` 复数标题(协议层会拦截)
- 禁止 `on_reject` 指向当前或之后的 step(只能向前跳)
- 禁止 LLM 在工作流内部使用 `__jump_to__` 类字段(铁律一)
- 禁止动态拼接字段名(input 必须是字面量)

### 4.4 变量解析与传递

变量在 `**Input**:` 中用 `key: source_var_name` 的形式声明:

```
**Input**:
- file_path: source_path        # 把 context['source_path'] 注入到 file_path 参数
- mode: "rb"                     # 字面量(不被识别为变量)
- meta?: optional_meta           # 可选输入,unbound 不报错
```

**Runner 通过 `parser.replace_variables` 把 `step.content` 里的 `{{var_name}}` 引用替换为实际值**(用于 LLM Skill 的 prompt 注入)。变量解析作用于:
1. step.inputs 的 value(变量映射)
2. step.content 中的 `{{var_name}}` 引用

### 4.5 三种特殊 Step 模式

#### 模式 A:线性步骤(最常见)

```markdown
## Step 1: ...
**Action**: file_reader
**Input**: ...
**Output**: file_content
---
## Step 2: ...
**Action**: llm_prompt_call
**Input**: file_content
**Output**: summary
```

#### 模式 B:Evaluator + on_reject 修复循环

```markdown
## Step 2: 生成产物
**Action**: llm_generator_call
**Output**: artifact

## Step 3: 评审产物
**Action**: llm_evaluator_call
**Input**: artifact
**Output**: evaluator_report
**on_reject**: 2     # REJECTED 时回 Step 2 重生成
```

#### 模式 C:子工作流调用

```markdown
## Step 1: 调用子流程
**Action**: sub_workflow_call
**Workflow**: workflows/dev/foo.step.md
**Input**:
  source: my_data
**Output**:
  result: child_output    # 把子流程的 child_output 映射到当前的 result
```

---

## 5. 协议层 + DSL 的整体保护链

```
用户(或 LLM)写 .step.md
        │
        ▼
   Parser 解析为 dict
        │
        ▼
   Normalizer 归一化(legacy 兼容,标题单复数)
        │
        ▼
   WorkflowModel 构造(Pydantic 字段级 validator + extra=allow)
        │  失败 → ProtocolSchemaError(结构错)
        ▼
   Gatekeeper 硬规则(action / on_reject / inputs 可达 / outputs 非空 / id 唯一)
        │  失败 → ProtocolReport(errors)
        ▼
   DryRun(模拟执行,变量依赖图)
        │  失败 → DryRunResult(status=failed)
        ▼
   SecurityScan(危险关键词 + 标记审计)
        │  违规 → ProtocolReport(violations)
        ▼
   ─────────── 进入注册阶段 ───────────
        │
        ▼
   WorkflowRegistry 写入 dev/ + index.json
        │
        ▼
   Runner 自动回放(:memory: 起新 Runner 真跑一次)
        │  失败 → 注册回滚
        ▼
   注册成功,workflow_id 生效
```

**这一整条链是 MyWorkflow"生成物可执行"承诺的工程兑现。** 任何一关失败都不会进入下一关,且失败原因都是结构化错误,可以被 Generator 修复循环消费。

---

## 6. 协议错误的回流(关键工程闭环)

协议层不只是"判官",还是 LLM 的"错题本"。具体机制:

```
Generator 生成产物
        │
        ▼
   ProtocolService.pre_register_check
        │  失败
        ▼
   ProtocolReport(errors=[
       {code: "STEP_ON_REJECT_NOT_BACKWARD",
        message: "on_reject must point to an earlier step id, got: 5",
        location: "step:3",
        suggestion: "Use a step id smaller than the current step for retry loop."},
       ...
   ])
        │
        ▼
   Evaluator 把这些 error 包装成 EvaluatorReport.defects
   (category="protocol", severity="blocker")
        │
        ▼
   status="REJECTED" 触发 on_reject
        │
        ▼
   Runner 跳回 Generator
        │
        ▼
   下一轮 Generator 看到 prev_defects 包含具体协议错误及修复建议
        │
        ▼
   Generator 修复后再生成
```

**这条闭环是协议层的"价值放大器"**:不是简单地拒绝,而是给 LLM 一个结构化的、可执行的修复目标。

---

## 7. 协议变更治理

任何涉及以下内容的变更必须先登记后合入:
- `protocol/models.py` 的 Schema 字段
- `protocol/gatekeeper.py` 的硬规则
- `protocol/dry_run.py` 的契约逻辑
- `protocol/error_codes.py` 的错误码(尤其码值和语义)
- Generator/Evaluator Prompt 中关于结构化输出的契约

**配套测试:** 重构期间每次 PR 必跑:
```bash
uv run pytest tests/integration/test_m3_closure_gates.py -q
uv run pytest tests/integration/test_dsl_cutover_gates.py -q
```

这两个 gate 测试是协议层的"宪法守护"。

---

## 8. 给"复现这个系统"的提示

如果要让 LLM 从零复现 MyWorkflow,**协议层和 DSL 是最优先复现的两件事**。原因:
- 协议层定义清楚后,所有上游模块的接口就被天然约束;
- DSL 定义清楚后,Parser / Generator / Evaluator 才有共同语言;
- 这两件事先做完,Runner / Skill / Champion 都可以平行展开。

**最小可复现脚手架(按顺序):**
1. 实现 `models.py` 三个 Pydantic 类 + 必要 validator
2. 实现 `error_codes.py` + `report.py`
3. 实现 `gatekeeper.py` 的 11 条规则
4. 实现 `dry_run.py` 的变量依赖图
5. 实现 `security_scan.py` 的两组关键词
6. 实现 `service.py` 编排
7. 写 `.step.md` 的 Parser(Markdown 三段式)
8. 写两个示范 `.step.md`(线性 + on_reject 循环)
9. 用 unit 测试覆盖以上每一项

完成这九步后,系统已经具备"接收 .step.md → 协议校验 → 报告问题"的完整能力,Runner 和 Skill 都可以在此基础上独立开发。

---

→ 接下来阅读 **03 · 运行时与 Harness 哲学** 了解 LLM 安全笼子的全貌。
