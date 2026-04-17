# MyWorkflow 设计档案 · 03 · 运行时与 Harness 哲学

> 读前置:00 · 顶层概览、01 · 架构与目录、02 · 协议层与 DSL
> 本文档目标:讲清楚 Runner 主循环的工程实现、Harness 三层防御体系、五层幻觉防御、安全审计手段、鲁棒性设计——这些是 MyWorkflow 在评审中最值得展示的"工程深度"部分。

---

## 1. Harness 思想:本系统的"灵魂"

### 1.1 什么是 Harness

> **Harness(脚手架/挽具) = 一套用代码约束 LLM 在安全笼子里干活的工程结构。**
>
> LLM 是不可信的"高产但易幻觉"的执行单元,系统的全部设计是围绕"如何让一个不可信的智能体产出可信的工程产物"展开的。

Harness 不是一个模块,是一种贯穿全系统的设计思想。在 MyWorkflow 里,它体现为**三层递进的防御体系**:

```
┌────────────────────────────────────────────────────────────────┐
│  Harness Layer 1 — 输入侧约束 (Pre-LLM)                          │
│    "在 LLM 开口之前,把它的可能性空间压到最小"                    │
│  ─────────────────────────────────────────────                  │
│  - Planner 已拆解的 WorkflowBlueprint(不开放任务,只填空)        │
│  - SkillCard 注入的能力清单(LLM 知道有哪些 Lego 块)             │
│  - few-shot 示例工作流(明确什么样是对的)                        │
│  - DSL 字段规则内嵌 Prompt(命名规则、单复数、可选标记)            │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Harness Layer 2 — 输出侧拦截 (Post-LLM)                         │
│    "LLM 说完了,但能不能生效要过五道闸"                          │
│  ─────────────────────────────────────────────                  │
│  - Pydantic 结构化输出(物理阻止字段缺失/类型错)                  │
│  - Action 字段 Validator(物理阻止幻觉技能名)                    │
│  - Gatekeeper 硬规则(11 条静态结构检查)                         │
│  - DryRun 变量依赖图(模拟执行,提前发现不可达变量)               │
│  - SecurityScan 危险关键词扫描(强制 [DANGER]/[CONFIRM] 标记)    │
│  - RuntimeAssertions 前后置断言(运行时最后一道防线)              │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Harness Layer 3 — 执行侧自愈 (Loop & Recover)                   │
│    "失败不是终点,是修复循环的起点"                              │
│  ─────────────────────────────────────────────                  │
│  - on_reject 跳转(由 Runner 解释 .step.md 声明)                 │
│  - Escalation Ladder(jump_back_counters 计数,L1→L4)            │
│  - Context Reset(chat_history = [],清记忆防幻觉积累)            │
│  - prev_defects 注入(下一轮 LLM 看到上一轮的具体错误)           │
│  - L4 人工阻断(连续 4 轮失败强制中止)                           │
│  - 断点续传(按 run_id 恢复,中途崩溃不丢工作)                  │
│  - Champion 复用(成功产物指纹化存档,下次相似需求秒级返回)       │
└────────────────────────────────────────────────────────────────┘
```

每一层独立有效,叠加形成**深度防御**。

### 1.2 为什么 Harness 是真正的核心创新

很多 Agent 框架在做"幻觉对抗",但通常是单点的:
- 用 JSON Schema 约束输出 → 解决了"格式幻觉",没解决"语义幻觉"
- 用 Function Call → 解决了"接口幻觉",没解决"参数幻觉"  
- 用更好的 Prompt → 解决了"理解幻觉",没解决"组合幻觉"

MyWorkflow 把它**体系化**了:从输入侧约束、输出侧拦截到执行侧自愈,每一层都有具体技术对应。Escalation Ladder + Context Reset + L4 阻断这套组合,是真在生产里跑出来的经验,不是 PPT 概念。

---

## 2. Runner 主循环详解

### 2.1 Runner 的职责边界

**Runner 必须做的:**
- 解析工作流文件(通过 Parser)
- 按顺序遍历 step
- 每步执行前后做断言、condition 求值、状态持久化
- 解释 on_reject 实现路由跳转
- 错误处理(SkillNotFoundError 硬失败,其他异常通过 ErrorPolicy)

**Runner 严格不能做的(铁律):**
- 不能知道任何具体工作流名字(违反铁律七)
- 不能让 LLM 决定路由(违反铁律一)
- 不能软跳过未知 Skill(违反铁律二)
- 不能把业务逻辑(Champion / 注册)写在自己里(重构后通过 ExecutionHooks 注入)

### 2.2 主循环骨架(伪代码)

```python
async def run(self, run_id=None):
    await self.state_store.connect()
    try:
        # ── 1. 解析 + 类型化 ──
        workflow_model, parsed = self.protocol_service.parse_workflow_file(self.filepath)
        steps = parsed['steps']
        workflow_name = workflow_model.metadata.name
        
        current_run_id = run_id or str(uuid.uuid4())
        start_step_id = 1
        
        # ── 2. 断点续传 ──
        if run_id:
            state = await self.state_store.load_run_state(current_run_id)
            if state:
                self.context.update(state.get("context", {}))
                start_step_id = state.get("current_step_id", 1)
                latest_step = await self.state_store.load_latest_step_state(
                    current_run_id, status="success"
                )
                if latest_step:
                    self.context.update(latest_step.get("full_context", {}))
                    start_step_id = max(start_step_id, latest_step["step_id"] + 1)
        
        # ── 3. 持久化初始状态 ──
        await self.state_store.save_run_state(
            current_run_id, workflow_name, "running", start_step_id, self.context
        )
        
        self.context.setdefault('prev_defects', [])
        self.context.setdefault('escalation_level', 1)
        current_step_index = start_step_id - 1
        jump_back_counters = {}   # Escalation Ladder 计数器
        
        # ── 4. 主循环 ──
        while current_step_index < len(steps):
            step = steps[current_step_index]
            
            # 4.a Champion 复用(通过 Hook 触发,Runner 不知道业务语义)
            await self._fire_hook("on_step_start", current_run_id, step, self.context)
            
            # 4.b Condition 求值(simpleeval 沙盒)
            if step.get('condition'):
                try:
                    if not simple_eval(step['condition'], names=self.context):
                        current_step_index += 1
                        continue
                except NameNotDefined:
                    # 变量未就绪 = 条件不满足 = 跳过
                    current_step_index += 1
                    continue
            
            # 4.c 持久化锚点(崩溃恢复)
            await self.state_store.save_run_state(
                current_run_id, workflow_name, "running", step['id'], self.context
            )
            
            # 4.d 前置断言
            self.protocol_service.validate_runtime_step_inputs(step, self.context)
            
            # 4.e 变量注入
            text_context = self.parser.replace_variables(step['content'], self.context)
            
            # 4.f 技能调度
            skill_name = step['action']
            try:
                skill = self.skill_registry.get(skill_name)   # 抛 SkillNotFoundError
                output = await execute_with_policy(
                    skill_name,
                    skill.execute_step if hasattr(skill, 'execute_step') else skill.execute,
                    step_or_text, self.context,
                )
                output = output or {}
                self.context.update(output)
                
                # 4.g 后置断言
                self.protocol_service.validate_runtime_step_outputs(step, output, self.context)
                
                # 4.h 持久化成功状态
                await self.state_store.save_step_state(
                    current_run_id, step['id'], "success", output, self.context
                )
                
                # 4.i Hook 通知
                await self._fire_hook("on_step_end", current_run_id, step, output, self.context)
                
                # 4.j on_reject 路由(只看当轮 output,不读 context 历史)
                report_dict = self._extract_evaluator_report(output)
                if report_dict and report_dict.get("status") == "REJECTED":
                    target_id = step.get('on_reject')
                    if target_id is not None:
                        # Escalation Ladder
                        jump_back_counters[target_id] = jump_back_counters.get(target_id, 0) + 1
                        current_escalation = jump_back_counters[target_id]
                        
                        # L4 人工阻断
                        if current_escalation >= 4:
                            raise Exception(f"Step {target_id} 连续被打回 4 次,请人工干预。")
                        
                        # 注入 escalation 信息 + Context Reset
                        self.context["escalation_level"] = current_escalation
                        self.context["prev_defects"] = report_dict.get("defects", [])
                        self.context.pop("evaluator_report", None)   # 防误跳
                        self.context["chat_history"] = []            # 清记忆
                        
                        # 跳转
                        target_index = next(
                            (i for i, s in enumerate(steps) if s['id'] == target_id), -1
                        )
                        if target_index == -1:
                            raise Exception(f"on_reject 目标 Step {target_id} 不存在。")
                        current_step_index = target_index
                        continue
            
            except SkillNotFoundError as e:
                # 硬失败,不软跳过(铁律二)
                await self._persist_failure(current_run_id, step, e)
                raise
            except Exception as e:
                await self._persist_failure(current_run_id, step, e)
                raise
            
            current_step_index += 1
        
        # ── 5. 工作流完成 ──
        await self._fire_hook("on_workflow_complete", current_run_id, workflow_name, "completed", self.context)
        await self.state_store.save_run_state(
            current_run_id, workflow_name, "completed", len(steps), self.context
        )
        
        return {"run_id": current_run_id, "status": "success", "context": self.context}
    
    finally:
        await self.state_store.close()
```

### 2.3 主循环里六个微妙细节(都来自踩坑)

#### 细节 1:`NameNotDefined` 当成"跳过"而非异常

```python
except NameNotDefined as e:
    # 条件变量尚未产生 → 语义上等同于条件不满足 → 跳过
```

把"未就绪"和"不满足"用同一种语义对待,大幅减少边界 case。否则 LLM 写出 `condition: prev_defects` 在第一轮(尚无 prev_defects)就崩了。

#### 细节 2:on_reject 只读当轮 output,不读 context 历史

```python
raw_report = output.get("evaluator_report")
# 不写成:raw_report = self.context.get("evaluator_report")
```

防止上一轮残留的 REJECTED 报告触发"假跳"。这个 bug 在 V2 出现过。

#### 细节 3:跳转后立即 `pop("evaluator_report")`

```python
self.context.pop("evaluator_report", None)
```

下一轮 Skill 如果忘了产出 evaluator_report,会被旧报告污染。pop 是防御性纪律。

#### 细节 4:跳转后清空 chat_history

```python
self.context["chat_history"] = []
```

防止 LLM 看到自己上一轮的错误回答,产生"我之前就这么说,这次也这么说吧"的认知锚定。**实测显著提升修复成功率**。

#### 细节 5:`escalation_level` 注入下一轮 LLM

下一轮 Generator/Evaluator 知道"这是第 N 次重试,你必须更严格",Prompt 可以根据 escalation_level 调整严厉程度。

#### 细节 6:L4 阻断是异常,不是返回

```python
if current_escalation >= 4:
    raise Exception(...)
```

阻断必须中断主循环并被持久化为 failed 状态,等待人工。如果用 return,调用方可能不知道这是异常退出。

---

## 3. 五层幻觉防御体系

| 层次 | 手段 | 防御的具体问题 | 实现位置 |
|------|------|--------------|---------|
| 第一层 | Pydantic Validator 约束 action 字段 | LLM 物理上无法生成不在白名单的技能名 | `WorkflowStepSpec.action` (Annotated[str, AfterValidator]) |
| 第二层 | Generator Prompt 内嵌 SkillCard(名称+用途+输入输出) | LLM 知道技能能做什么,不会误用 | `prompts/generator_system_v1.md` |
| 第三层 | Generator Prompt 内嵌 few-shot 示例工作流 | LLM 模仿正确格式,减少 DSL 格式幻觉 | `prompts/examples/*.step.md` |
| 第四层 | Gatekeeper + DryRun 拦截不合规产物,错误回流 | 生成后立即校验,错误原因反馈触发修复循环 | `protocol/gatekeeper.py` + `protocol/dry_run.py` |
| 第五层 | RuntimeAssertions 前后置断言 | 运行时最后防线,发现 LLM 引用了根本不可达的变量 | `protocol/runtime_assertions.py` |

**这五层的关键性质:**
- 每一层独立有效(单独使用就有价值)
- 越靠前的层成本越低(Validator 是 O(1),DryRun 是 O(N))
- 越靠后的层兜底范围越广(RuntimeAssertions 能发现编译期看不到的 bug)
- 任何一层失败都不会沉默(都有结构化错误,可被回流给 LLM 修复)

### 3.1 SkillCard 注入格式(给 Generator 的"能力清单")

```
### file_reader
用途:读取本地文件内容,返回文本字符串
何时使用:需要读取文件、配置、模板等本地资源时
不要用于:写入、修改或删除文件(使用 file_writer)
输入:file_path: str(必填)
输出:file_content: str;error: str(可选,读取失败时)

### sub_workflow_call
用途:调用另一个已注册的子工作流,传递变量并接收结果
特殊字段:需要声明 **Workflow**: <path> 字段指定子工作流路径
输入:由子工作流 frontmatter inputs 决定
输出:由子工作流 frontmatter outputs 决定
```

这种格式比"技能名列表"提升数倍的 LLM 选择正确率。每个字段都对应一个具体的"减少误用"目标。

---

## 4. LLM 权力边界三条铁律

```
LLM 可以做的:
  ✓ 生成 WorkflowModel 的内容字段(步骤名称、描述、输入输出声明)
  ✓ 给出语义性质量评审(四维打分、缺陷描述、修复建议)
  ✓ 根据 SkillCard 描述选择合适的技能名称

LLM 不可以做的:
  ✗ 决定流程跳转 — 路由权在 Runner(on_reject 由开发者在 .step.md 声明)
  ✗ 使用不在 SkillRegistry 白名单里的技能名 — 物理层面由 Validator 阻止
  ✗ 绕过协议层 — Evaluator APPROVED ≠ 可注册,注册前必须过 Gatekeeper + DryRun
  ✗ 影响引擎运行参数 — Generator 输出只包含内容字段,引擎行为参数不暴露给 LLM
```

**这是一个不对称权力结构:代码可以否决 LLM 的 APPROVED,反之不行。这种不对称就是安全。**

---

## 5. 三角色 LLM 闭环

```
                ┌──────────────┐
                │   用户需求    │ (自然语言)
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │   Planner    │ — 战略层:把需求拆解为 WorkflowBlueprint
                │              │   输出 = 蓝图(步骤数、技能选型、依赖关系)
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │   Generator  │ — 战术层:把蓝图实现为可执行 .step.md
                │              │   输出 = WorkflowModel(Pydantic 直出)
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
            ┌──→│  Evaluator   │ — 审查层:四维 rubric 评分 + 静态检查
            │   │              │   输出 = EvaluatorReport
            │   └──────┬───────┘
            │          │
            │   APPROVED?
            │     │      │
       REJECTED   ✗      ✓
            │             │
            │             ▼
            │       ┌──────────────┐
            │       │   注册流程    │
            │       └──────────────┘
            │
            └─── on_reject 跳回 Generator
                 (escalation_level += 1)
                 (chat_history = [])
                 (prev_defects 注入)
```

### 5.1 三角色为什么要分离

| 优势 | 解释 |
|------|------|
| Prompt 简单 | 每个角色的 Prompt 只关心一件事,易维护、易调优 |
| 责任清晰 | bug 定位明确(蓝图问题找 Planner,代码问题找 Generator,质量问题找 Evaluator)|
| 可独立演进 | 换一个角色的模型不影响其他(可以让 Planner 用更便宜的模型,Generator 用强模型)|
| 审计友好 | 每个角色的输出都有结构化 schema,可以单独 dump 出来审计 |

### 5.2 Evaluator 四维 Rubric

| 维度 | 权重 | 评估什么 |
|------|------|---------|
| logic_closure | 40% | 逻辑闭环(步骤间数据流是否完整、是否能达成目标)|
| safety_gate | 30% | 安全闸门(危险操作是否被正确标记)|
| engineering_quality | 20% | 工程质量(可维护性、清晰度)|
| persona_adherence | 10% | 角色一致性(是否符合 .step.md 声明的工作流意图)|

**强制 REJECTED 条件**(代码强制,Evaluator LLM 无法绕过):
- `static_scan` 命中 violations → 直接 REJECTED,不进入语义评分
- `pre_register_check` 失败 → 直接 REJECTED,defects 中包含 `category="protocol"` 项

---

## 6. 系统的鲁棒性设计

### 6.1 断点续传

**机制:**
- 每个 step 执行前后都写 StateStore(`save_run_state` + `save_step_state`)
- StateStore 用 SQLite,所有数据 JSON 序列化(不依赖 pickle)
- 启动时按 run_id 查 StateStore:有历史 → 恢复 context + 跳到下一步;无历史 → 全新执行

**为什么 JSON 不 pickle:**
- pickle 任何对象不可序列化都会整包丢失(铁律五)
- JSON 强制只存可序列化数据,迫使开发者把 context 写"扁",更安全
- JSON 跨语言,未来可换 StateStore 后端不破坏数据

**代码里的体现(`runner.py`):**
```python
state = await self.state_store.load_run_state(current_run_id)
if state:
    self.context.update(state.get("context", {}))
    start_step_id = state.get("current_step_id", 1)
    # 还要 hydrate 最后成功的 step
    latest_step = await self.state_store.load_latest_step_state(
        current_run_id, status="success"
    )
    if latest_step:
        self.context.update(latest_step.get("full_context", {}))
        start_step_id = max(start_step_id, latest_step["step_id"] + 1)
```

### 6.2 三级幂等性策略(`error_policy.py`)

```python
class IdempotencyLevel(Enum):
    L0 = "L0"  # 强幂等:无副作用,可安全自动重试(读文件、纯查询)
    L1 = "L1"  # 条件幂等:执行前需检查 guard(写文件、Git 提交)
    L2 = "L2"  # 非幂等:不可自动重试(发邮件、删文件、高危操作)

SKILL_IDEMPOTENCY = {
    "file_reader": IdempotencyLevel.L0,
    "file_writer": IdempotencyLevel.L1,
    "llm_prompt_call": IdempotencyLevel.L0,
    "llm_planner_call": IdempotencyLevel.L0,
    "llm_generator_call": IdempotencyLevel.L0,
    "llm_evaluator_call": IdempotencyLevel.L0,
    "shell_executor": IdempotencyLevel.L2,
}
```

**`execute_with_policy` 的核心逻辑:**
- L0/L1 → 用 tenacity 做指数退避重试
- L2 → 强行拦截自动重试,失败直接抛出(进入 CONFIRM 流程)
- `SkillNotFoundError` 在任何级别都不重试,直接传播(铁律二)

**为什么这是安全的核心:** L2 的存在保证了**任何有副作用的操作不会因为重试而执行多次**,这是工程级安全的最小要求。

### 6.3 硬失败原则

```python
class SkillNotFoundError(Exception):
    pass

# Runner 主循环:
try:
    skill = self.skill_registry.get(skill_name)   # 未知技能直接抛
except SkillNotFoundError as e:
    await self._persist_failure(...)
    raise   # 不软跳过,立即终止
```

**为什么硬失败:** "未知技能"意味着工作流和系统状态根本不一致,继续执行只会导致更多隐藏 bug。立即终止 + 持久化失败原因是最负责任的做法。

### 6.4 注册前自动回放

**机制:** Meta Workflow 完成后,如果产物被 APPROVED 且通过协议校验,调用 `_attempt_generated_workflow_replay`:

```python
async def _attempt_generated_workflow_replay(self, workflow_path: str) -> None:
    workflow_model, _ = self.protocol_service.parse_workflow_file(workflow_path)
    required_inputs = self.protocol_service.infer_required_inputs(workflow_model)
    replay_context = with_runtime_input_defaults(self.context)
    missing_inputs = [x for x in required_inputs if x not in replay_context]
    if missing_inputs:
        return   # 缺输入则跳过回放,只标 skipped
    
    # 用 :memory: SQLite + 全新 Runner 真跑一次
    replay_runner = Runner(
        filepath=workflow_path,
        initial_context=replay_context,
        db_path=":memory:",
        ...
    )
    replay_result = await replay_runner.run()
    self.context["generated_workflow_replay"] = {"status": replay_result["status"], ...}
```

**这是把"可执行"从承诺变成事实的关键工程动作。**对应底线 1:"不是生成了,是可运行"。

---

## 7. 安全审计的所有手段一览

| 手段 | 检查时机 | 检查内容 |
|------|---------|---------|
| Pydantic Schema 校验 | 解析时 | 字段类型 / 必填 / 取值范围 |
| Action Validator | Pydantic 解析时 | action 必须在 SkillRegistry 白名单 |
| Gatekeeper 11 条规则 | 注册前 | id 唯一 / on_reject 向前 / outputs 非空 等 |
| DryRun 变量依赖图 | 注册前 | 变量可达性 / 步骤可达性 |
| SecurityScan 危险关键词 | 注册前 + 注册时 | DANGER 关键词必须有 [DANGER] 标记 / CONFIRM 必须有 [CONFIRM] |
| RuntimeAssertions 前置 | 每步执行前 | inputs 字段在 context 里有定义 |
| RuntimeAssertions 后置 | 每步执行后 | output 字段实际产出了声明的变量 |
| simpleeval 沙盒 | condition 求值时 | 不允许任意 Python 求值,只允许安全表达式 |
| `execute_with_policy` 包装 | 每个 Skill 调用 | L2 强制拦截重试,L0/L1 限次 |
| StateStore JSON 持久化 | 每步执行前后 | 强制可序列化,防止 pickle 丢数据 |
| L4 人工阻断 | 连续 4 轮 REJECTED 后 | 强制中止,等待人工 |
| 注册前自动回放 | 注册时 | 产物在 :memory: 真跑一次,失败则不注册 |
| `run_meta` 审计字段 | 注册时 | 写入 protocol_summary、protocol_report、dry_run 全量结果供事后审计 |
| Context Pressure 观测 | 每步执行前后 | 采样 token 压力,超阈值 log warning(为重构后 hard reset 做准备)|

**这套手段的共同特征:**
- 每个手段都有明确的检查时机(不是"随便检查")
- 每个手段都有明确的失败行为(report 错误码 / 抛异常 / 阻止注册)
- 每个手段都不依赖 LLM(都是确定性代码)

---

## 8. Champion 机制(自演化的关键)

### 8.1 双指纹

```python
def _requirement_fingerprint(self) -> str:
    requirement = self.context.get("requirement", "")
    return hashlib.sha256(requirement.encode()).hexdigest()

def _blueprint_fingerprint(self) -> str:
    blueprint = self.context.get("workflow_blueprint", {})
    canonical = json.dumps(blueprint, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
```

### 8.2 复用流程

```
新一轮 Meta Workflow 启动
        │
        ▼
   Step 1: Planner 跑完 → blueprint 已生成
        │
        ▼
   Step 2 进入前(由 Hook 触发):
   计算 (req_fp, bp_fp) 双指纹
        │
        ▼
   StateStore.load_latest_champion_by_composite(req_fp, bp_fp)
        │
        ├── 命中 + status=APPROVED
        │   ↓
        │   hydrate context(final_artifact, evaluator_report)
        │   set __reuse_champion__=True
        │   ↓
        │   Step 2: 跳过(_try_replay_champion_for_meta)
        │   Step 3: 跳过(直接复用 evaluator_report)
        │   ↓
        │   秒级到达注册阶段
        │
        └── 未命中
            ↓
            正常执行 Generator + Evaluator
            ↓
            完成后:_update_champion 比较 score
            如果新产物更优,更新 Champion 表
```

### 8.3 Champion 的工程价值

- **省 token**:相同需求 + 相同 blueprint 不重复生成,直接复用
- **省时间**:跳过 Generator + Evaluator,从分钟级降到秒级
- **越用越聪明**:历史成功产物作为知识资产沉淀,系统跑得越多越快
- **可降级**:任何时候清空 Champion 表系统也能正常工作,只是慢

---

## 9. 系统的"自指"性质(系统本身是一个工作流)

这是 MyWorkflow 最优雅的一面。

```
系统的 Meta Workflow 自身也是一份 .step.md:
  workflows/meta/main_workflow.step.md
        │
        ▼
  它声明了 4 个 sub_workflow_call 步骤:
    Step 1: workflow_planner.step.md
    Step 2: workflow_designer.step.md   (Generator)
    Step 3: quality_evaluator.step.md   (Evaluator)
    Step 4: 注册步骤(Hook 触发)
        │
        ▼
  Runner 跑 main_workflow.step.md → 生成新的 .step.md
        │
        ▼
  新的 .step.md 又能被同一个 Runner 跑通
        │
        ▼
  → 系统是自描述、自演化的有机体
```

**这种自指设计的工程价值:**
- Runner 的稳定性被双向验证(既要能跑用户工作流,又要能跑生成工作流的元工作流)
- 协议层的规则被双向验证(既要能审用户产物,又要能审 Meta Workflow 自己)
- 新增 Meta Workflow 能力 = 改 .step.md,不改 Runner — 完美符合"数据驱动、引擎不变"的设计

---

## 10. 复现这个系统的最小可用清单

如果要从零复现一个功能相近的系统,**优先级从高到低**实现:

1. 协议层 + DSL Parser(详见 02 文档) — 这是地基,做对了一切就稳
2. SkillRegistry + 最简 Skill(file_reader / file_writer / llm_prompt_call)
3. StateStore(SQLite,JSON 序列化)
4. ErrorPolicy(三级幂等 + tenacity)
5. Runner 主循环(按本文档 2.2 节伪代码)
6. 写一个 hello_world.step.md 跑通端到端
7. 加 LLMPlannerCall / LLMGeneratorCall / LLMEvaluatorCall 三个 LLM Skill
8. 写四个 meta workflow .step.md,跑通生成链路
9. 加 ChampionTracker 通过 Hook 接入
10. 加注册前自动回放
11. 加 ContextManager + 五层防御的剩余部分

每一步都是独立可测试的里程碑。整个系统的复杂度被分摊到 11 个可独立验证的步骤里——这本身也是 Harness 思想的体现:**让人类工程师也在一个安全笼子里干活,每步都有反馈**。

---

— 全部设计档案至此完结 —

> 若需要更深入了解某模块,请直接阅读对应的源码文件。代码本身是最准确的文档。
