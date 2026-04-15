# MyWorkflow 设计档案 · 00 · 顶层概览

> 文档版本:v1.0 · 设计基线
> 适用读者:产品/架构评审、新成员入门、未来用 LLM 重新生成同类系统时的"系统观"输入
> 配套阅读:
> - 01 · 架构与目录
> - 02 · 协议层与 DSL
> - 03 · 运行时与 Harness 哲学

---

## 1. 一句话定位

> **MyWorkflow 是一个以 Markdown DSL(`.step.md`)为工作流格式、以三角色 LLM 闭环为生成引擎、以协议层为治理中枢、以 Runner 为执行状态机的"工作流自动生成与执行系统"。**

系统本身即是一个工作流:接收自然语言需求,输出可被本引擎重复执行的标准化 `.step.md` 工作流。

## 2. 它解决什么问题

当前主流的"AI Agent / Workflow 框架"普遍存在三个缺陷:

1. **规则散在 Prompt 里**:LLM 既当运动员又当裁判,无法被工程性地审计和测试。
2. **生成物不一定可执行**:很多框架满足于"LLM 输出了一个 plan",但这个 plan 是否真的能跑、能否在变量上自洽,没有强校验。
3. **失败后没有自愈结构**:LLM 给了一个不合规产物,系统通常只能"再问一次",没有结构化的"反馈—修复—验证"循环。

MyWorkflow 用三件事系统性地回应这三个缺陷:

1. **协议层(`protocol/`)**:把所有"可以由代码确定地判定对错"的规则抽出来,作为独立子系统,LLM 没有否决权。
2. **注册前自动回放(`_attempt_generated_workflow_replay`)**:生成的工作流必须在 `:memory:` SQLite 上真跑一次,通过才能进 index——把"能跑"从承诺变成事实。
3. **三角色闭环 + Escalation Ladder**:Planner / Generator / Evaluator 三个 LLM 角色 + Runner 的循环跳转 + L4 人工阻断,把"质量不够"从故障变成可控的修复循环。

## 3. 核心设计哲学(四条不可妥协的底线)

```
底线 1:生成的工作流必须可被本引擎正确运行,能完成用户需求
       —— 不是"生成了",是"可运行"

底线 2:安全检查(静态扫描 + 运行时拦截)必须能阻断危险操作
       —— 代码判定,不交给 LLM

底线 3:上下文与状态持久化必须可恢复
       —— 崩溃后按 run_id 恢复,不允许整包丢弃

底线 4:所有可以由代码确定性验证的事情,绝对不交给 LLM 判断
```

这四条底线是系统的"宪法",任何模块设计、任何 PR 必须不违反。

## 4. 八条工程铁律(从 V1–V4 真实踩坑提炼)

每一条都来自实际 bug,不是空想。

| 编号 | 铁律 | 反例(不允许的写法) |
|------|------|-------------------|
| 一 | 路由权在 Runner,不在 LLM | LLM 输出 `__jump_to__` 字段触发跳转 |
| 二 | 未知 Skill 必须硬失败 | `if skill_name not in registry: continue` |
| 三 | 协议规则单点归属 | gatekeeper / security_scan / generator 三处各写一份 action 检查 |
| 四 | 注册前必须验证执行契约 | 写 dev/ 文件成功 → 直接写 index,不跑 dry_run |
| 五 | 恢复能力必须可证明 | 用 `pickle.dumps(context)`,某个对象不可序列化整包丢失 |
| 六 | 治理策略必须测试化 | "我们约定不要这么写"(没有测试守护) |
| 七 | 引擎不知道任何具体工作流 | `if workflow_name == "Meta Main Workflow": ...` |
| 八 | LLM 生成物走结构化路径 | `LLM → render_markdown → Parser → dict`(文本往返) |

## 5. 系统的两条主链路

### 链路 A · 生成工作流(Meta Workflow 自演化链路)

```
用户自然语言需求
       │
       ▼
   Planner   ─────── 输出 WorkflowBlueprint(JSON)
       │
       ▼
  Generator  ─────── 输出 WorkflowModel(Pydantic)
       │
       ▼
  Evaluator  ─────── 四维 rubric + SecurityScan + Protocol 静态校验
       │             ──────────────────────────────────────
       │             APPROVED  →  注册流程
       │             REJECTED  →  on_reject 跳回 Generator
       │                          (Escalation Ladder ≤ 4 轮)
       │
       ▼
  注册流程   ─────── Gatekeeper + DryRun + WriteIndex
       │             ↓
       │             自动回放(:memory: 起新 Runner 验证可跑)
       │
       ▼
   workflow_id 注册成功,可被同一引擎重复调用
```

### 链路 B · 调用工作流(已注册工作流执行)

```
用户输入 workflow_id + inputs
       │
       ▼
   Runner 主循环
       │
       ├─ 断点续传(按 run_id 从 StateStore 恢复)
       │
       ├─ 每步:
       │    ConditionEvaluator(simpleeval 沙盒)
       │    RuntimeAssertions.validate_inputs
       │    Skill.execute (经 execute_with_policy 包裹幂等/重试)
       │    RuntimeAssertions.validate_outputs
       │    StateStore.save_step_state
       │
       ├─ on_reject 跳转(由 Runner 解释 .step.md 声明)
       │
       └─ 全部完成 → save_run_state(completed)
       │
       ▼
   RunResult(run_id, status, context)
```

## 6. 关键设计抉择速览

| 抉择 | 选择 | 替代方案 | 理由 |
|------|------|---------|------|
| 工作流格式 | Markdown 带 frontmatter | JSON / YAML / Python DSL | 同一份 artifact 同时是文档、配置、可被 LLM 生成,人机协同成本最低 |
| 类型系统 | Pydantic 全链路 | dataclass / dict | Pydantic 既是类型也是校验,与协议层天然契合 |
| 路由控制权 | Runner 解释 `.step.md` 声明 | LLM 输出跳转字段 | 可审计、可测试、不被幻觉污染 |
| 条件求值 | simpleeval 沙盒 | Python `eval()` | 防止 Prompt 注入或恶意条件 |
| 重试机制 | tenacity + 三级幂等性(L0/L1/L2) | 简单 N 次重试 | L2(非幂等)不允许自动重试,这是安全底线 |
| StateStore 实现 | SQLite(默认)/ 抽象接口可换 | 文件 JSON / Redis | 单机够用,接口隔离便于未来切换 |
| Champion 复用 | 双指纹(requirement + blueprint) | 单一缓存 key | 粒度精细,减少误命中 |
| 三角色拆分 | Planner / Generator / Evaluator 分离 | 单一 LLM 包揽 | 每个角色 Prompt 简单、可独立调优、责任清晰 |

## 7. 项目重点解决的问题(逐一对应模块)

| 问题 | 解决手段 | 关键模块 |
|------|---------|---------|
| LLM 幻觉导致不可执行产物 | 五层幻觉防御 + Escalation Ladder | `protocol/` + `runner.py` 的 on_reject 段 |
| 生成物的规范性 | `.step.md` DSL + Pydantic Schema + Normalizer | `parser.py` + `protocol/models.py` + `protocol/normalizer.py` |
| 系统鲁棒性 | 断点续传 + 三级幂等性 + 硬失败原则 | `state_store.py` + `error_policy.py` + `skill_registry.py` |
| 安全审计 | 危险关键词扫描 + simpleeval 沙盒 + 协议层报告 | `protocol/security_scan.py` + `runner.py`(`simple_eval` 调用) |
| 路由权防滥用 | `on_reject` 在 `.step.md` 声明,Runner 解释 | `runner.py` 的 on_reject 段 + 铁律一 |
| 冷启动到自演化 | Champion 双指纹复用 | `runner.py` 的 `_try_enable_composite_champion_reuse` |
| 文本往返信息损失 | (重构后)Generator 直出 WorkflowModel | 重构方向二、铁律八 |

## 8. 当前版本边界(暂不做的事)

明确写下"不做",比"做了什么"更能展现工程纪律:

- ❌ **动态生成技能**:LLM 生成 Python 代码动态加载执行。安全沙箱难做,且无法通过协议层校验。
- ❌ **完整 FastAPI server**:预留 `api/` 目录但不实装 endpoint。
- ❌ **多 Agent 并行执行**:当前严格顺序执行,等步骤间 DAG 依赖明确后再考虑。
- ❌ **跨设备分布式 StateStore**:单机 SQLite 完全够用。
- ❌ **自动学习/微调 LLM**:Champion 是"复用",不是"训练"。

## 9. 系统的"灵魂"是什么

如果只能用一句话告诉别人 MyWorkflow 和其他 Agent 框架的根本不同:

> **它把"约束 LLM 在安全笼子里干活的脚手架(Harness)"作为头等公民,而不是把 LLM 当作万能解决方案。**

具体体现为四个特征:

1. **代码做最终判官,LLM 做提议者**:协议层一票否决权。
2. **结构化优先,文本兜底**:全链路 Pydantic,Markdown 只在人机交互边界出现。
3. **失败可循环,循环有上界**:Escalation Ladder 4 轮,L4 阻断转人工。
4. **系统是数据驱动的**:`.step.md` 是数据,Runner 是引擎,新增能力只需写新 `.step.md` 和新 Skill,不动引擎。

---

→ 接下来阅读 **01 · 架构与目录** 了解八层结构与依赖关系。
