# llm_factory.py → 移入 infra/ 并扩展重构实现细节

## 一、文件搬移

从 agent/engine/ 移入 agent/infra/，原因：LLM 客户端是外部依赖的适配器，属于基础设施层。

## 二、新增 LLMClientRegistry（单例化）

现有 build_chat_model() 每次被调用都新建一个 LangChain 客户端对象，导致每个 Skill 实例化时都有初始化开销，也无法复用底层 httpx 连接池。
新增 LLMClientRegistry 类，维护 _cache: dict[tuple, Any]，key 是 (provider, model_name, temperature) 三元组。
get_or_create(model_name, temperature) -> Any：先查缓存，命中直接返回；未命中则调原有的 build_chat_model() 逻辑创建并存入缓存。
LLMClientRegistry 作为模块级单例实例（_registry = LLMClientRegistry()），Skill 通过 from agent.infra.llm_factory import get_chat_model 调用，get_chat_model 是包装了 registry 的工厂函数。
线程安全：由于 Python asyncio 是单线程事件循环，dict 操作本身线程安全，不需要加锁。但如果未来引入多线程执行器，需要加 threading.Lock。[待定：是否需要考虑线程安全，当前 asyncio 单线程模型下不需要]

## 三、现有函数保持但调用方式改变

resolve_llm_provider()、resolve_model_name()：保持逻辑不变，但从 os.environ.get(...) 改为从 config/settings.py 的 Settings 对象读取。load_dotenv() 的调用移到 settings.py 初始化时统一做，不在每个函数里重复调用。
build_chat_model() 保留但标注为内部使用，外部调用改用 get_chat_model()（走 registry 缓存）。
build_structured_output_model() 和 resolve_structured_output_kwargs() 保持逻辑不变，搬移到新文件即可。DeepSeek 的 method: "function_calling" 兼容特殊处理保留。

