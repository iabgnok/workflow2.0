# MyWorkflow 设计档案与重构补充 · 总目录

本目录包含两套独立但互补的文档:

## 📘 一、完整设计档案(项目交付物)

按"如何理解一个系统"的认知顺序组织。建议**按编号顺序阅读**,但每份都可独立看。

| 文件 | 内容 | 适合谁 |
|------|------|--------|
| [`00_OVERVIEW.md`](./00_OVERVIEW.md) | 顶层概览:定位、底线、铁律、两条主链路、设计哲学 | 所有人,5 分钟读完即可建立全局观 |
| [`01_ARCHITECTURE.md`](./01_ARCHITECTURE.md) | 八层架构、依赖方向、目录结构、数据类型流图 | 架构师、新成员、需要复现系统骨架的人 |
| [`02_PROTOCOL_AND_DSL.md`](./02_PROTOCOL_AND_DSL.md) | **协议层 + `.step.md` DSL 完整规范**(本系统最核心创新) | 想理解"为什么这个系统比别人靠谱"的人;复现协议层时必读 |
| [`03_RUNTIME_AND_HARNESS.md`](./03_RUNTIME_AND_HARNESS.md) | Runner 主循环、Harness 三层防御、五层幻觉防御、安全审计、Champion、自指设计 | 评审场景的"工程深度展示";关注 LLM 安全性的人 |

**这套档案的设计目标是:足够详尽到能直接交给一个聪明的 AI,让它大差不差地复现一个功能相近的系统。**

## 📕 二、重构方案补充(对已有重构纲领的查漏补缺)

| 文件 | 内容 |
|------|------|
| [`重构方案补充_REFACTOR_ADDENDUM.md`](./重构方案补充_REFACTOR_ADDENDUM.md) | 8 条对原《MyWorkflow 重构设计纲领》的补充,只查漏补缺,不增加复杂度 |

8 条补充速览:

| 编号 | 一句话总结 |
|------|-----------|
| 1 | 协议错误通过 EvaluatorReport.defects(category="protocol") 走 on_reject 路径 |
| 2 | ExecutionHooks 五条契约:async / 无返回值 / 异常隔离 / FIFO / context 只读 |
| 3 | ContextManager 抛 ContextOverflowSignal,Runner 中介,ChampionTracker 在 Hook 里写 handoff |
| 4 | action 字段用 `Annotated[str, AfterValidator]` 而不是真 Literal |
| 5 | WorkflowRegistry 启动时 verify_consistency,孤儿条目降级不删除 |
| 6 | 实施顺序插入第 5.5 步,先打通错误回流再做直出 |
| 7 | 一次性冻结 8 个"小待定"决策(prompts 格式、StateStore 9 方法等) |
| 8 | 每步 PR 维护 Deprecation Manifest,第 8 步收尾清零 |

---

## 阅读建议

### 给评委的 5 分钟览读路径

1. `00_OVERVIEW.md` 第 1-5 节(定位、底线、铁律、链路图)
2. `03_RUNTIME_AND_HARNESS.md` 第 1 节(Harness 思想)+ 第 10 节(评审讲解素材清单)

### 给新成员的入门路径

按 00 → 01 → 02 → 03 顺序通读一遍。

### 给 LLM 复现系统的输入

- 优先级 1:`02_PROTOCOL_AND_DSL.md` 第 8 节"给复现这个系统的提示" + 全文
- 优先级 2:`01_ARCHITECTURE.md` 第 4 节"关键文件一览"
- 优先级 3:`03_RUNTIME_AND_HARNESS.md` 第 2.2 节"主循环骨架伪代码" + 第 11 节"复现最小清单"
