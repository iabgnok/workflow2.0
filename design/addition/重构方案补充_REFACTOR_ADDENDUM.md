# MyWorkflow 重构方案补充纲领

> 版本：Refactor v1.0 — Addendum 01
> 状态：对《MyWorkflow 重构设计纲领》(Refactor v1.0) 的查漏补缺
> 适用范围：与重构主纲领并行生效；二者不一致时，本补充作为"细化补丁"，不替换主纲领的总体方向
> 编写原则：**只查漏补缺，不增加新需求；不引入新模块，不扩大复杂度**

---

## 0. 本补充的定位

主纲领回答了**"重构成什么样"**,本补充回答**"重构落地时几个隐式约定怎么显式化"**。

具体来说,补充以下八件事——它们在主纲领里都已经"暗含"或"提了一句没展开",但落地时如果不补完整,会出现:
- 多人理解不一致;
- 下游模块对接时发现"原来 A 模块这么期望我";
- 实现完一遍后才发现某个回路没接通,要返工。

每条补充都标注了**所属主纲领位置 / 改动范围 / 风险等级 / 接入到主实施顺序的哪一步**。

---

## 目录

- [补充 1：协议层错误回流统一走 on_reject 路径](#补充-1协议层错误回流统一走-on_reject-路径)
- [补充 2：ExecutionHooks 接口契约的最小封口](#补充-2executionhooks-接口契约的最小封口)
- [补充 3：ContextManager hard reset 与 ChampionTracker 的协作约定](#补充-3contextmanager-hard-reset-与-championtracker-的协作约定)
- [补充 4：Skill 白名单的"动态枚举"用 validator 实现而非真 Literal](#补充-4skill-白名单的动态枚举用-validator-实现而非真-literal)
- [补充 5：WorkflowRegistry 与 dev/ 目录的一致性兜底](#补充-5workflowregistry-与-dev-目录的一致性兜底)
- [补充 6：Generator 直出与协议错误回流的依赖前置](#补充-6generator-直出与协议错误回流的依赖前置)
- [补充 7：散落的"小待定"清单一次性冻结](#补充-7散落的小待定清单一次性冻结)
- [补充 8：重构灰度策略 — Deprecation Manifest](#补充-8重构灰度策略--deprecation-manifest)
- [附录 A：补充项与主实施顺序的接入映射](#附录-a补充项与主实施顺序的接入映射)
- [附录 B：补充项一览速查表](#附录-b补充项一览速查表)

---

## 补充 1：协议层错误回流统一走 on_reject 路径

**主纲领位置:** 第 3 节方向二、第 6.1 节链路图、第 9 节 P0「协议层错误回流」
**改动范围:** Evaluator 输出契约 + Runner 主循环少量适配
**风险等级:** 中(影响 Evaluator 与 Runner 的语义对齐,但实现量很小)
**接入主实施顺序:** **必须在第 6 步「Generator 结构化路径打通」之前完成**(参见补充 6)

### 1.1 问题

主纲领反复提到"Gatekeeper / DryRun 失败的 ProtocolReport errors 回流给 Generator,合并进 prev_defects",但**没说清楚回流的物理路径**——是 Generator 内部自循环,还是经过 Runner 主循环和 on_reject 跳转?

这两种实现差别巨大,且无法事后切换:

| 路径 | 优点 | 缺点 |
|------|------|------|
| Generator 内部自循环 | Generator 调用方无感知,接口干净 | 内循环要重建一套幂等/重试/escalation,等于在能力层造一个 mini-Runner;打破"Runner 是唯一控制流"的铁律 |
| 走 on_reject 跳转 | 复用 Runner 现有的 Escalation Ladder/L4 阻断/Context Reset 机制,统一控制流 | 要求 EvaluatorReport 能表达"协议层失败"这第三态 |

### 1.2 决策

**必须走 on_reject 路径**。

理由:
- 已有的 Escalation Ladder(`jump_back_counters`)+ Context Reset(`chat_history = []`)+ L4 阻断已经是一套验证过的循环逻辑,没有理由再造一套。
- 主纲领铁律一明确"路由权在 Runner",内循环本质上是把路由权下放给 Generator,违反铁律。
- 协议层失败和语义评审失败在用户视角是同一类问题——都是"产物质量不够,需要重做"。

### 1.3 落地实现

**EvaluatorReport 增加协议失败语义(零字段新增)。** 通过复用现有 `status="REJECTED"` + `defects` 字段,在 `defects` 中追加协议层错误项,并在每条 defect 上标注来源:

```python
# EvaluatorReport.defects 中每一项的结构(已有):
# {
#   "category": "logic_closure" | "safety_gate" | "engineering_quality" | "persona_adherence",
#   "severity": "blocker" | "major" | "minor",
#   "message": str,
#   "suggestion": str,
# }

# 仅约定:protocol 失败时 category 取固定值 "protocol",
# 表示这是协议层强制 REJECTED,不是 LLM 语义评审结果。
{
    "category": "protocol",          # 新增的固定取值,不新增字段
    "severity": "blocker",           # 协议失败一律 blocker
    "message": "STEP_INVALID_ACTION at step:3 - Step action is missing or unknown.",
    "suggestion": "Ensure **Action** is declared and maps to a known skill.",
}
```

**评审流程的优先级硬规则:**

```
quality_evaluator.step.md 内的执行序列(由 LLMEvaluatorCall 实现):
1. SecurityScan 命中 violations  → 直接 status=REJECTED,跳过 LLM 调用
2. ProtocolService.pre_register_check 失败 → 直接 status=REJECTED,跳过 LLM 调用
3. 以上都通过 → LLM 做四维 rubric 评分,可能 APPROVED 也可能 REJECTED
```

注意:第 2 步是新加的——当前 `evaluate_workflow_file` 已经做了 Gatekeeper + SecurityScan + 可选 DryRun,本次补充只是把这个结果**显式映射成 EvaluatorReport.defects**,让 Generator 下一轮能在 `prev_defects` 里看见。

**Runner 端零改动。** 因为 on_reject 跳转只看 `evaluator_report.status == "REJECTED"`,不关心 REJECTED 的原因——这条原则保持不变,符合"Runner 不知道业务语义"的铁律。

### 1.4 测试要求

新增一个 integration 测试 `test_protocol_failure_routes_through_on_reject.py`:
- 构造一个会被 Gatekeeper 拒绝的 WorkflowModel(如 `on_reject` 指向不存在的 step_id);
- 让它走完 Evaluator → on_reject → 回到 Generator;
- 断言下一轮 Generator 调用时 `prev_defects` 包含 `category="protocol"` 的条目;
- 断言 Escalation Ladder 计数器正常递增,L4 在第 4 轮触发。

---

## 补充 2:ExecutionHooks 接口契约的最小封口

**主纲领位置:** 第 4 节层 ②(协调层)、第 5 节目录结构 `execution_hooks.py`
**改动范围:** 一个新文件,约 30 行代码 + 文档约定
**风险等级:** 低(纯接口约束,没有运行时复杂逻辑)
**接入主实施顺序:** 第 4 步「Runner 拆分」时一并落地

### 2.1 问题

主纲领只写了三个 Hook 名字(`on_step_start` / `on_step_end` / `on_workflow_complete`),缺以下契约:
1. Hook 是 sync 还是 async?
2. 返回值会被 Runner 消费吗?能否影响主循环?
3. Hook 抛异常 Runner 怎么办?
4. 多个 Hook 注册时的顺序约定?
5. Hook 能不能修改 context?

不补这些,`ChampionTracker` 落地时会"想当然"地直接修改 `runner.context`,造成隐式耦合,这是当前 Runner 691 行的根本病因之一。

### 2.2 五条契约(写进 `execution_hooks.py` 模块 docstring,作为强约束)

```python
"""
ExecutionHooks 接口契约(与主纲领铁律七配套,任何实现必须遵守):

1. 异步性:所有 Hook 方法必须是 `async def`,Runner 用 `await` 调用。
   理由:Runner 主循环本身是 async,sync Hook 会阻塞事件循环。

2. 无返回值:Hook 方法签名固定为返回 None。Runner 不消费 Hook 返回值。
   不允许 Hook 通过返回值否决步骤、修改 context、改变路由。
   理由:路由权在 Runner(铁律一),Hook 只观察和触发副作用,不参与控制流。

3. 异常隔离:Hook 抛异常时,Runner 必须 catch + log warning + 写 telemetry,
   绝不传播给主循环。Hook 的 bug 不能让引擎崩。
   理由:业务编排层的稳定性低于引擎层,引擎不应被拖累。

4. 注册顺序 = 调用顺序:Runner 维护 hooks 列表,FIFO 执行。
   不允许 Hook 之间存在依赖(任何依赖必须在业务编排层内自行处理)。

5. context 只读:Hook 接收的 context 是一个 MappingProxyType 只读视图,
   或在传入前 deepcopy。Hook 想要持久化数据必须通过自己的 StateStore 资源。
   理由:Hook 偷偷改 context 是隐式耦合,等价于"业务逻辑回到引擎"。
"""
```

### 2.3 接口签名(冻结,不允许扩展)

```python
from typing import Protocol, Any, Mapping

class ExecutionHook(Protocol):
    async def on_step_start(
        self,
        run_id: str,
        step: Mapping[str, Any],
        context: Mapping[str, Any],   # 只读
    ) -> None: ...

    async def on_step_end(
        self,
        run_id: str,
        step: Mapping[str, Any],
        output: Mapping[str, Any],     # 只读
        context: Mapping[str, Any],    # 只读(已合并 output 后的)
    ) -> None: ...

    async def on_workflow_complete(
        self,
        run_id: str,
        workflow_name: str,
        status: str,                   # "completed" / "failed"
        context: Mapping[str, Any],    # 只读
    ) -> None: ...
```

### 2.4 ChampionTracker 配套要求

`ChampionTracker` 的所有写操作只能写到自己的 StateStore 表(`champion_json` / `run_meta`),不能写 `runner.context`。
当前 `runner.py` 中的 `_hydrate_champion_context` 把 `final_artifact` / `evaluator_report` 写回 `self.context`——这个行为在重构后改为:**ChampionTracker 写到 `run_meta`,Runner 在 run() 启动时读 `run_meta` 并 hydrate 一次**。这是 Hook 不能修改 context 这条契约的必然结果,等于把"复用 Champion"的发起权从 Hook 收回到 Runner。

---

## 补充 3:ContextManager hard reset 与 ChampionTracker 的协作约定

**主纲领位置:** 第 9 节 P0「ContextManager 真正闭环」+ 层 ⑤ ChampionTracker
**改动范围:** 一个信号(异常类)+ ChampionTracker 增加一个 Hook 实现
**风险等级:** 中(涉及跨层信号传递,接入点要明确,否则会变成隐式耦合)
**接入主实施顺序:** 第 8 步「ContextManager 真正闭环」

### 3.1 问题

主纲领里两件事各自合理但**没说怎么协作**:
- ContextManager 的 hard reset:"触发 handoff artifact → 新 Runner 恢复"
- ChampionTracker:`handoff_artifact` 由它构建

谁来"触发"?ContextManager 知不知道 handoff_artifact 长什么样?如果 ContextManager 自己构建,就和 ChampionTracker 重复;如果 ContextManager 直接调 ChampionTracker,就违反"基础设施层不依赖业务编排层"的依赖方向。

### 3.2 决策:用一个异常信号解耦,Runner 做中介

定义一个新异常:

```python
# agent/infra/context_manager.py
class ContextOverflowSignal(Exception):
    """
    ContextManager 检测到 hard reset 阈值后抛出此信号。
    Runner 捕获后:
      1. 调用 on_workflow_complete Hook,status="handed_off"
      2. 让 ChampionTracker(作为已注册 Hook)在 on_workflow_complete 里
         构建 handoff_artifact 并写入 StateStore.run_meta
      3. Runner 自身正常退出,返回 status="handed_off" + run_id
    
    新一轮启动由调用方(CLI/上层调度)发起,通过 run_id 恢复 handoff。
    """
    def __init__(self, run_id: str, pressure_ratio: float):
        self.run_id = run_id
        self.pressure_ratio = pressure_ratio
```

### 3.3 信号流向

```
ContextManager.check_pressure_or_signal(context, window)
    │ 检测到 ratio > hard_reset_threshold
    ▼
raise ContextOverflowSignal(run_id, ratio)
    │
    ▼
Runner 主循环 catch:
    │
    ├── 1. await self._fire_hooks("on_workflow_complete",
    │                              status="handed_off", ...)
    │
    ├── 2. ChampionTracker.on_workflow_complete 实现里:
    │        - 构建 handoff_artifact dict
    │        - state_store.save_run_meta(run_id, handoff_artifact=...)
    │
    ├── 3. await state_store.save_run_state(run_id, "handed_off", ...)
    │
    └── 4. return {"run_id": run_id, "status": "handed_off"}
        ↑ 调用方拿到这个状态,自行决定是否启动新 Runner 续跑
```

### 3.4 关键约束

- ContextManager **永远不直接 import** `ChampionTracker` 或任何业务编排层模块。
- 信号是单向的(ContextManager → Runner),不能反向。
- handoff_artifact 的 schema 由 ChampionTracker 单独定义,不在 ContextManager 里出现。
- Runner 捕获 `ContextOverflowSignal` 后**不重新启动**新 Runner,只持久化状态并退出。"恢复"是上层调度的职责,引擎不参与。

这个设计把"什么时候触发 hard reset"(基础设施层的 ContextManager)和"hard reset 时该保存什么"(业务编排层的 ChampionTracker)彻底解耦,二者只通过 Runner 这个中介间接对话。

---

## 补充 4:Skill 白名单的"动态枚举"用 validator 实现而非真 Literal

**主纲领位置:** 第 9 节 P0「Pydantic Literal 枚举 action 字段」、第 7.2 节五层防御第一层
**改动范围:** `WorkflowStepSpec.action` 字段类型注解 + 一个 validator
**风险等级:** 低(纯 Schema 实现技巧,不影响调用方)
**接入主实施顺序:** 第 3 步「skills/ 按类型重组 + SkillCard 声明」一并落地

### 4.1 问题

主纲领写"`WorkflowStepSpec.action 从 str 改为动态构建的 Literal 枚举`",但 `Literal` 在 Python 类型系统里是**导入时**确定的,而 SkillRegistry 是**运行时**扫描的——存在先有鸡还是先有蛋的问题。此外:
- 测试时怎么注入 mock skill?
- 用户自定义 skill 加进来要不要重建 Schema?
- LangChain `with_structured_output` 对动态 Literal 的支持因 provider 而异(尤其 OpenAI 的 strict mode 严格要求 schema 静态)。

### 4.2 决策:用 `Annotated[str, AfterValidator]` 替代真 Literal

```python
# agent/skills/llm/generator.py(或 protocol/models.py 中)
from typing import Annotated
from pydantic import AfterValidator

def _validate_action_in_registry(value: str) -> str:
    # 延迟 import 避免循环依赖
    from agent.engine.skill_registry import get_global_registry_snapshot
    registered = get_global_registry_snapshot()
    if value not in registered:
        raise ValueError(
            f"action '{value}' 不在已注册技能白名单中。"
            f"已注册:{sorted(registered)}"
        )
    return value

ActionName = Annotated[str, AfterValidator(_validate_action_in_registry)]

class WorkflowStepSpec(BaseModel):
    action: ActionName    # 替代原来的 str
    # ... 其他字段不变
```

### 4.3 优点

- 物理阻止 LLM 生成不在白名单的 action(违反时 Pydantic 抛 ValidationError,直接 REJECTED)。
- Schema 静态可序列化,不影响 OpenAI structured output 的兼容性(对外暴露的还是 `str`)。
- 测试时可以 monkeypatch `get_global_registry_snapshot` 注入 mock 集合。
- 用户自定义 skill 加入 SkillRegistry 后,validator 下一次调用自动看到——零重启。

### 4.4 必备配套

`SkillRegistry` 增加一个 `get_global_registry_snapshot() -> frozenset[str]` 模块级函数,返回当前已注册技能名集合的不可变快照。**只读不可变**这点关键,防止 validator 拿到的引用被外部修改。

---

## 补充 5:WorkflowRegistry 与 dev/ 目录的一致性兜底

**主纲领位置:** 第 5 节目录结构 + 层 ⑦
**改动范围:** WorkflowRegistry 增加一个方法 + 一个 CLI 子命令(可选)
**风险等级:** 低(纯防御性代码)
**接入主实施顺序:** 第 2 步「infra/ 层整合」时一并落地

### 5.1 问题

主纲领把 `index.json` 从 workflow 文件目录里挪出来(独立放到 `workflows/registry/`),理由是"独立后可以支持多索引、备份、迁移"。这个方向对,但**没说一致性怎么保证**:
- 用户手动删了 `dev/foo.step.md`,index 里会留脏条目;
- index 写成功但文件写失败(磁盘满、权限问题),会有孤儿索引;
- 多人协作时(虽然你现在是单人,但未来可能),两人同时注册可能写脏。

### 5.2 落地

`WorkflowRegistry.verify_consistency() -> ConsistencyReport`,启动时调用一次。

```python
@dataclass
class ConsistencyReport:
    orphaned_index_entries: list[str] = field(default_factory=list)  # index 里有但文件不在
    orphaned_files: list[str] = field(default_factory=list)          # 文件在但 index 没有
    repaired: bool = False                                            # 是否做了自动降级
```

**处理策略(写死,不可配置,降低复杂度):**

| 情况 | 自动处理 |
|------|----------|
| index 里有但文件不在 | 把该条目状态改为 `status="orphaned"`,**不删除**(防误伤),log warning |
| 文件在但 index 没有 | 不做任何事,只在 report 里列出,等待人工 `register` |

启动时调用:

```python
# 在 Runner __init__ 或 main.py 启动时
report = self.workflow_registry.verify_consistency()
if report.orphaned_index_entries:
    logger.warning(
        f"发现 {len(report.orphaned_index_entries)} 个孤儿索引条目,已降级为 orphaned。"
        f"详情:{report.orphaned_index_entries}"
    )
```

### 5.3 不做的事

- **不**自动删除孤儿条目(用户可能临时移走文件,删了就找不回)。
- **不**自动注册孤儿文件(注册必须经过协议层校验,自动行为会绕开校验)。
- **不**做并发锁(单机单用户场景没必要,引入锁等于引入死锁风险)。

如果未来有需要,加一个 CLI 子命令 `myworkflow registry repair` 让用户手动确认。这是 P2 级别,不阻塞重构。

---

## 补充 6:Generator 直出与协议错误回流的依赖前置

**主纲领位置:** 第 10.3 节实施顺序
**改动范围:** 调整实施顺序,不改设计
**风险等级:** 高(顺序错了会出现"直出后无法调试"的窘境)
**接入主实施顺序:** **修改主纲领 10.3 节的实施顺序**

### 6.1 问题

主纲领 10.3 节列的 8 步实施顺序里:
- 第 6 步:Generator 结构化路径打通(直出 WorkflowModel,消灭文本往返);
- 协议错误回流通路(补充 1)在主纲领里没有显式步骤,只是 P0 列表的一个条目。

如果第 6 步先于错误回流通路完成,会出现:
- 文本往返时,Generator 的 raw 输出至少在日志里能看到原文,Parser 失败时还能拿来定位;
- 直出后,Generator 输出的是 Pydantic 对象,失败时只看到 ValidationError;
- 此时如果协议层错误回流没接通,Generator 下一轮拿不到具体的协议失败原因——只看到上一轮 evaluator 给的语义反馈,而那条反馈可能根本没提协议失败。

调试体验**比文本往返时更差**,这是反直觉的回退。

### 6.2 决策:把"协议错误回流通路"作为第 6 步的前置步骤

修改后的实施顺序:

```
1. config/settings.py + protocol/utils.py(原)
2. infra/ 层整合(原)
3. skills/ 按类型重组 + SkillCard 声明(原)
4. Runner 拆分(原)
5. ChampionTracker 独立(原)
5.5(新增). 协议错误回流通路打通(补充 1)
   - EvaluatorReport.defects 增加 category="protocol" 约定
   - LLMEvaluatorCall 在 LLM 调用前先做 ProtocolService.pre_register_check
   - 失败时直接构造 REJECTED 报告,不调 LLM
   - 测试:test_protocol_failure_routes_through_on_reject.py
6. Generator 结构化路径打通(原)
7. Generator Prompt + Evaluator Prompt 强化(原)
8. ContextManager 真正闭环(原)
```

### 6.3 验证清单

在第 5.5 步完成后,第 6 步开工前必须确认:
- [ ] 构造一个故意违反 Gatekeeper 的 WorkflowModel,跑完整流程,Generator 第二轮的 `prev_defects` 里能看到 `category="protocol"` 的条目;
- [ ] Escalation Ladder 计数器在协议失败时正常 +1;
- [ ] L4 阻断在协议失败连续 4 轮后正常触发;
- [ ] 整个流程不需要 Generator 直出能力,文本往返路径仍工作。

---

## 补充 7:散落的"小待定"清单一次性冻结

主纲领里散落几处"待定"或"二选一",在这里一次性冻结决策,避免实施时反复纠结。

| 待定项 | 主纲领位置 | 冻结决策 | 理由 |
|--------|-----------|---------|------|
| `prompts/` 目录用 `.md` 还是 `.jinja2` | 5 节目录、9 节 P1 | **统一 `.md`**,占位符用最简单的 `{var}` 单花括号(Python `str.format`)|不引入 jinja 依赖,避免 Prompt 模板里写出图灵完备的逻辑(违反"约束前置")|
| few-shot 示例放哪里 | 5 节 / 9 节 P1 | **`prompts/examples/`**,不放 `workflows/templates/` | 消费者是 Prompt 不是 Runner;放 `workflows/` 会让 SkillRegistry/WorkflowRegistry 误扫到 |
| `AbstractStateStore` 的方法清单 | 9 节 P1 | **冻结为 9 个方法**(见下) | 现有 `StateStore` 已经在用这 9 个,先冻结再演进 |
| `Skill[InputT, OutputT]` 基类还是 `AgentSpec` | 4 节层 ④ | **`AgentSpec` 是声明类,`Skill` 是执行基类**,二者并存 | AgentSpec 集中元数据(声明性);Skill 提供 `execute` / `execute_step`(行为);通过 `AgentSpec.skill_class` 关联 |
| Hook 是 Protocol 还是 ABC | 4 节 / 补充 2 | **Protocol(structural typing)** | 鸭子类型,业务编排层无需 import 引擎模块 |
| LLMClientRegistry 的缓存 key | 9 节 P1 | **`(provider, model_name, temperature, json_mode)` 四元组** | 加 `json_mode` 因为结构化输出和普通输出的 client 配置可能不同 |
| WorkflowModel 的 `extra` 字段策略 | 协议层 | **保持当前 `extra="allow"`** | 已在 `WorkflowMetadata`/`WorkflowStep`/`WorkflowModel` 三处统一允许;迁移期容错 legacy 字段 |
| 重构期间是否保留 `_render_markdown()` | 铁律八 | **保留为 dev 工具**,标 `@deprecated`,只在 dump 调试时使用 | 完全删除会丢失人类可读的中间产物;但生产路径绝不调用 |

### `AbstractStateStore` 冻结的 9 个方法

```python
class AbstractStateStore(ABC):
    @abstractmethod
    async def connect(self) -> None: ...
    
    @abstractmethod
    async def close(self) -> None: ...
    
    @abstractmethod
    async def save_run_state(
        self, run_id: str, workflow_name: str, status: str,
        current_step_id: int, context: dict
    ) -> None: ...
    
    @abstractmethod
    async def save_step_state(
        self, run_id: str, step_id: int, status: str,
        output: dict, context: dict
    ) -> None: ...
    
    @abstractmethod
    async def load_run_state(self, run_id: str) -> dict | None: ...
    
    @abstractmethod
    async def load_latest_step_state(
        self, run_id: str, status: str | None = None
    ) -> dict | None: ...
    
    @abstractmethod
    async def save_run_meta(self, run_id: str, **meta_fields) -> None: ...
    
    @abstractmethod
    async def load_run_meta(self, run_id: str) -> dict | None: ...
    
    @abstractmethod
    async def load_latest_champion_by_composite(
        self, requirement_fingerprint: str, blueprint_fingerprint: str
    ) -> dict | None: ...
```

冻结后变更必须走协议变更登记(主纲领 10.1 节)。

---

## 补充 8:重构灰度策略 — Deprecation Manifest

**主纲领位置:** 10.3 节实施顺序
**改动范围:** 流程要求,无代码改动
**风险等级:** 低,但不做会在第 8 步收尾时发现两套并存难拆
**接入主实施顺序:** 从第 1 步开始持续执行,第 8 步收尾时清零

### 8.1 问题

主纲领 8 步顺序每步都说"独立可回归",这是好事。但经验上最容易出问题的是:**重构期间为了兼容老路径,引入新路径时保留旧路径,最终新旧并存难以拆除**。

例如第 3 步重组 skills 时,为了不影响第 2 步引入的 infra,可能保留 `agent/engine/llm_factory.py` 的 import shim,然后这个 shim 一直保留到第 8 步,变成永久遗物。

### 8.2 落地:每步 PR 维护一个 Deprecation Manifest

每个重构步骤的 PR 描述里**必须**包含一个段落:

```markdown
## Deprecation Manifest

本 PR 引入的 deprecated 路径(必须在指定步骤前删除):

| Deprecated 项 | 引入原因 | 必须删除节点 | 删除责任人 |
|---------------|---------|-------------|-----------|
| `agent.engine.llm_factory` import shim | 第 3 步未完成,skills/ 还在用旧路径 | 第 3 步 PR | 同一人 |
| `WorkflowParser._render_markdown()` 未删 | 第 6 步未完成,LLM 生成物还经文本往返 | 第 6 步 PR | 同一人 |

本 PR 删除的 deprecated 项:

| 项 | 引入步骤 | 替代方案 |
|----|---------|---------|
| (无) | - | - |
```

### 8.3 第 8 步收尾的 Definition of Done

第 8 步 PR 合并前必须满足:**所有历史 PR 引入的 Deprecation Manifest 项,要么已删除,要么转入"长期遗留"清单并附理由**。"长期遗留"清单不能多于 3 项,每项必须有"为什么不能删"的具体说明。

### 8.4 工具支持(可选,P2)

写一个简单的脚本扫描代码库里 `# DEPRECATED:` 注释,生成实时清单。但不强求,文本约定就够了。

---

## 附录 A:补充项与主实施顺序的接入映射

```
主实施顺序                              本补充项接入
────────────────────────────────────   ──────────────────────────────────
1. config/settings.py + protocol/utils  无新接入(开始执行补充 8 的灰度策略)
2. infra/ 层整合                        + 补充 5(WorkflowRegistry 一致性兜底)
3. skills/ 按类型重组 + SkillCard       + 补充 4(Skill 白名单 validator)
4. Runner 拆分                          + 补充 2(ExecutionHooks 接口契约)
5. ChampionTracker 独立                 (补充 2 的 Hook 实现一并落地)
5.5(新增). 协议错误回流通路打通          + 补充 1(全部内容)
6. Generator 结构化路径打通             (前置依赖补充 6 的顺序调整已生效)
7. Generator Prompt + Evaluator Prompt  + 补充 7(Prompt 模板格式冻结)
8. ContextManager 真正闭环              + 补充 3(ContextOverflowSignal)
                                        + 补充 8 收尾(Deprecation 清零)
```

---

## 附录 B:补充项一览速查表

| 编号 | 一句话总结 | 改动量 | 风险 | 必须做 |
|------|-----------|-------|------|--------|
| 补充 1 | 协议错误通过 EvaluatorReport.defects(category="protocol") 走 on_reject 路径 | 中 | 中 | 是 |
| 补充 2 | ExecutionHooks 五条契约:async / 无返回值 / 异常隔离 / FIFO / context 只读 | 小 | 低 | 是 |
| 补充 3 | ContextManager 抛 ContextOverflowSignal,Runner 中介,ChampionTracker 在 Hook 里写 handoff | 中 | 中 | 是 |
| 补充 4 | action 字段用 `Annotated[str, AfterValidator]` 而不是真 Literal | 小 | 低 | 是 |
| 补充 5 | WorkflowRegistry 启动时 verify_consistency,孤儿条目降级不删除 | 小 | 低 | 是 |
| 补充 6 | 实施顺序插入第 5.5 步,先打通错误回流再做直出 | 流程 | 高 | 是 |
| 补充 7 | 一次性冻结 8 个"小待定"决策(prompts 格式、StateStore 9 方法等) | 文档 | 低 | 是 |
| 补充 8 | 每步 PR 维护 Deprecation Manifest,第 8 步收尾清零 | 流程 | 低 | 是 |

— 补充纲领结束 —
