## 1. 编排层目录

- [x] 1.1 创建 `new_src/agent/orchestration/__init__.py`

## 2. ChampionTracker 实现

- [x] 2.1 创建 `new_src/agent/orchestration/champion_tracker.py`
- [x] 2.2 实现 `__init__`（接受 state_store, workflow_registry, protocol_service, workflows_root, index_path）
- [x] 2.3 实现 `on_run_start()` — 复合指纹查找 + Champion 注水
- [x] 2.4 实现 `on_step_before()` — 复用跳过判断（step 2/3）
- [x] 2.5 实现 `on_step_after()` — evaluator_report 处理 + Champion 更新
- [x] 2.6 实现 `on_workflow_complete()` — 注册 + 回放 + 错误回流
- [x] 2.7 实现私有方法：_requirement_fingerprint, _blueprint_fingerprint, _extract_blueprint_features, _report_score

## 3. 集成

- [x] 3.1 更新 main.py 入口，构造 ChampionTracker 并传入 Runner
- [x] 3.2 编写 ChampionTracker 的单元测试（各钩子方法）
- [x] 3.3 编写 ChampionTracker + Runner 的集成测试（完整 Meta Workflow 循环）
