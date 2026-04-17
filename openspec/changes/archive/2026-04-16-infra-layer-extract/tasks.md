## 1. 目录结构创建

- [x] 1.1 创建 `new_src/agent/infra/__init__.py`
- [x] 1.2 创建各文件的空占位（确认目录结构）

## 2. StateStore 迁移与抽象化

- [x] 2.1 创建 `new_src/agent/infra/state_store.py`，定义 `AbstractStateStore` 抽象基类（9 个 async 方法）
- [x] 2.2 将 `old_src/agent/engine/state_store.py` 迁移为 `SQLiteStateStore(AbstractStateStore)`
- [x] 2.3 确保所有序列化使用 JSON（移除任何 pickle 依赖）
- [x] 2.4 编写 AbstractStateStore 接口测试和 SQLiteStateStore 实现测试

## 3. LLM 工厂迁移与注册中心

- [x] 3.1 创建 `new_src/agent/infra/llm_factory.py`，迁移现有 resolve/build 函数
- [x] 3.2 新增 `LLMClientRegistry` 单例类，实现 `get_or_create()` 缓存逻辑
- [x] 3.3 配置读取改为从 `settings` 对象获取
- [x] 3.4 编写客户端缓存的单元测试

## 4. SkillRegistry 迁移与增强

- [x] 4.1 创建 `new_src/agent/infra/skill_registry.py`，迁移现有扫描逻辑
- [x] 4.2 改造 `scan()` 为递归扫描 `skills/llm/`、`skills/io/`、`skills/flow/`
- [x] 4.3 新增 `build_skill_manifest() -> str` 方法
- [x] 4.4 新增 `SkillNotFoundError` 异常类
- [x] 4.5 编写递归扫描和 manifest 生成的测试

## 5. 其他适配器迁移

- [x] 5.1 迁移 `workflow_registry.py`，新增 `register_workflow_model()` 方法
- [x] 5.2 迁移 `context_manager.py`，新增 `perform_soft_reset()` 和 `perform_hard_reset()`
- [x] 5.3 迁移 `variable_mapper.py`，新增 `VariableMappingError`
- [x] 5.4 迁移 `error_policy.py`（三级幂等性策略保持不变）

## 6. 验证

- [x] 6.1 确认所有 infra/ 文件不 import engine/ 层的模块（依赖方向正确）
- [x] 6.2 运行全部迁移后的单元测试
