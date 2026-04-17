"""agent.infra — 外部资源适配层。

包含所有与外部系统交互的适配器：持久化存储、LLM 客户端、技能注册表、
工作流注册表、上下文管理器、变量映射器和错误策略。

依赖方向：infra 层不依赖 engine 执行层（Runner/StepExecutor 等），
          engine 层依赖 infra 层的接口和实现。
"""
