## Context

铁律七要求"引擎不知道任何具体工作流"。当前 Runner 硬编码了 Meta Workflow 的 Champion 逻辑，违反了这条铁律。ChampionTracker 通过 Hook 接口与 Runner 交互，是唯一知道 Meta Workflow 业务语义的模块。

## Goals / Non-Goals

**Goals:**
- 将 12 个 Champion 相关方法从 Runner 迁移到 ChampionTracker
- ChampionTracker 通过 ExecutionHooks 四个钩子驱动
- 复合复用：requirement_fingerprint + blueprint_fingerprint 双指纹匹配
- 协议错误回流：注册失败时将 ProtocolReport 错误合并进 prev_defects

**Non-Goals:**
- 不改变 Champion 的业务逻辑（指纹算法、分数比较、回放流程）
- 不支持多个 Hook 实例同时注入（当前一个 Runner 对应一个 hooks）
- 不处理非 Meta Workflow 场景的 Champion 逻辑（只有 Meta Workflow 需要）

## Decisions

### Decision 1: ChampionTracker 继承 ExecutionHooks 而非实现接口
**选择**: 类继承
**理由**: ExecutionHooks 是一个有默认空实现的基类，ChampionTracker 只 override 需要的钩子方法，其余默认为空操作。比 Protocol/Interface 模式更简洁。

### Decision 2: on_step_before 使用硬编码步骤 ID 判断
**选择**: step.id == 2 / step.id == 3 作为复用跳过条件
**理由**: Meta Workflow 的步骤结构（1:Planner, 2:Designer, 3:Evaluator）是固定的。虽然硬编码不优雅，但 Meta Workflow 不会频繁变更，过度抽象（如步骤标签匹配）增加复杂度但收益甚微。代码中加注释说明。

### Decision 3: 协议错误回流通过 prev_defects 字段
**选择**: 注册失败时将 protocol_report.errors_as_defects() 合并进 context["prev_defects"]
**理由**: Generator 的 Prompt 已有处理 prev_defects 的逻辑（含 [PROTOCOL:...] 标签区分来源），复用现有机制成本最低。

## Risks / Trade-offs

- **[Risk] 硬编码步骤 ID 在 Meta Workflow 修改时失效**: 如果 Meta Workflow 步骤顺序变更，ChampionTracker 会出错。→ **Mitigation**: 步骤 ID 以常量形式定义在文件顶部，修改 Meta Workflow 时同步更新。
- **[Risk] 单 hooks 实例限制**: 如果未来需要多个 Hook（如日志 Hook + Champion Hook），当前架构不支持。→ **Mitigation**: 可以在 Runner 中引入 CompositeHooks 模式（遍历多个 hooks），但目前 YAGNI。
