# config/settings.py（新增）

## 一、为什么需要这个文件

这是整个重构里收益最高、风险最低的改动。当前以下内容散落在至少 6 个文件里：LLM_PROVIDER、LLM_MODEL、LLM_API_KEY（llm_factory.py）、CONTEXT_WINDOW_TOKENS（runner.py）、soft_ratio、hard_ratio（context_manager.py）、DEFAULT_POLICIES、SKILL_IDEMPOTENCY（error_policy.py）、db_path（runner.__init__）、workflows_root、index_path（runner.__init__、workflow_registry.__init__）。

## 二、使用 pydantic-settings

from pydantic_settings import BaseSettings，定义 class Settings(BaseSettings)，所有字段带类型标注和默认值，从环境变量自动加载（pydantic-settings 会处理 os.environ 和 .env 文件读取，不需要手动 load_dotenv）。

## 三、字段清单

LLM 相关：

llm_provider: str = "gemini"（对应 LLM_PROVIDER）
llm_model: str = ""（空字符串表示由 provider 决定）
llm_api_key: str = ""
llm_base_url: str = ""
gemini_model: str = "gemini-2.0-flash-lite"
gemini_api_key: str = ""
google_api_key: str = ""
deepseek_model: str = "deepseek-chat"
deepseek_api_key: str = ""
deepseek_base_url: str = "https://api.deepseek.com/v1"
openai_model: str = "gpt-4o-mini"
openai_api_key: str = ""
openai_base_url: str = ""

引擎相关：

context_window_tokens: int = 120000
context_soft_ratio: float = 0.60
context_hard_ratio: float = 0.80
context_soft_reset_max_history: int = 8

路径相关：

db_path: str = ""（空时由代码根据 __file__ 推导默认路径）
workflows_root: str = ""（同上）
skills_root: str = ""（同上）
prompts_root: str = ""（同上）

默认工作流输入（替代 with_runtime_input_defaults 的硬编码）：

default_workflow_inputs: dict[str, Any] = Field(default_factory=lambda: {"repo_path": "", "readme_path": "README.md", "output_path": "output.txt", "retry_count": 0, "max_retries": 3})

注意：repo_path 的默认值是 os.getcwd()，但 pydantic-settings 不支持在字段默认值里调函数，需要在 with_runtime_input_defaults 里读取 settings 字段时单独处理 repo_path 的 os.getcwd() 默认值。[待定：repo_path 动态默认值的处理方式]

## 四、模块级单例和访问方式

settings = Settings() 模块级单例，文件末尾定义。
全项目通过 from config.settings import settings 访问，不再各自读 os.environ。
model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)：自动读取 .env 文件，环境变量名大小写不敏感。

## 五、路径的动态推导

对于 db_path、workflows_root、skills_root、prompts_root 这类路径，空字符串时由各自的使用方在代码里推导默认值（保持现有的 os.path.join(os.path.dirname(__file__), ...) 逻辑），settings 只是提供一个 override 入口。这样不需要 settings 文件知道项目的绝对路径。

