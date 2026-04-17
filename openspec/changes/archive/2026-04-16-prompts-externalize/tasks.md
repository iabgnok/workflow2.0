## 1. 目录和文件创建

- [x] 1.1 创建 `new_src/prompts/` 目录
- [x] 1.2 创建 `generator_system_v1.md`（角色定义、DSL 规则、变量命名、少样本示例、技能白名单占位符、修复模式、禁止行为）
- [x] 1.3 创建 `evaluator_system_v1.md`（角色定义、四维评分规则含权重阈值、静态扫描规则、升级降级规则、输出契约）
- [x] 1.4 创建 `planner_system_v1.md`（角色定义、拆分判断、输出字段规范、禁止行为）

## 2. 加载机制验证

- [x] 2.1 验证 `LLMAgentSpec._load_system_prompt()` 能正确加载 prompts/ 目录下的文件
- [x] 2.2 编写缓存行为的单元测试
- [x] 2.3 验证 settings.prompts_root 路径拼接正确
