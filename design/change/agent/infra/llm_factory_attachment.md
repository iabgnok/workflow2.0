# infra/llm_factory.py（从 engine/llm_factory.py 搬移，扩展 LLMClientRegistry）

## 一、LLMClientRegistry 的实现细节

类结构：

_cache: dict[tuple[str, str, float], Any]：key 是 (provider, model_name, temperature) 三元组，value 是 LangChain 客户端对象
get_or_create(model_name: str | None, temperature: float) -> Any：主入口，计算 key，查缓存命中直接返回，未命中则调 _build(model_name, temperature) 创建并存入缓存
_build(model_name, temperature) -> Any：内部调原有的 build_chat_model 逻辑创建新客户端
clear() 方法：清空缓存，主要用于测试场景重置状态

模块级单例：_registry = LLMClientRegistry()，对外暴露 get_chat_model(model_name, temperature) 函数，调 _registry.get_or_create(model_name, temperature)。
build_structured_output_model 不需要走缓存（它的结果依赖 schema 类型，每次绑定不同 schema），保持每次创建新的 runnable。但底层的 LangChain 客户端走缓存，所以不会重复初始化 HTTP client。

## 二、resolve_llm_provider 和 resolve_model_name 的 settings 集成

两个函数里的 os.environ.get(...) 改为从 config/settings.py 的 Settings 对象读取。load_dotenv() 调用移到 settings.py 初始化时统一执行，这两个函数里不再调用。
Settings 对象在模块导入时初始化，resolve_llm_provider() 和 resolve_model_name() 变成纯读取 settings 字段的函数。

## 三、函数保留的完整列表

保留：resolve_llm_provider()、resolve_model_name()、build_chat_model()（内部实现，不推荐外部调用）、get_chat_model()（新增，推荐外部调用）、build_structured_output_model()、resolve_structured_output_kwargs()。