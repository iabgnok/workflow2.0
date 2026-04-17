"""
集中配置管理模块，基于 pydantic-settings。

支持环境变量和 .env 文件自动加载，提供类型验证和模块级单例。
"""
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目全局配置。

    所有字段均可通过同名环境变量（不区分大小写）或 .env 文件覆盖。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── LLM 通用配置 ──────────────────────────────────────────────────────────
    llm_provider: str = "deepseek"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_model: str = "gemini-2.0-flash-lite"
    gemini_api_key: str = ""

    # ── DeepSeek ──────────────────────────────────────────────────────────────
    deepseek_model: str = "deepseek-chat"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    openai_base_url: str = ""

    # ── 引擎参数 ──────────────────────────────────────────────────────────────
    context_window_tokens: int = 120000
    context_soft_ratio: float = 0.60
    context_hard_ratio: float = 0.80
    soft_reset_max_history: int = 10
    min_quality_score: int = 60
    structured_validation_max_retries: int = 1

    # ── 路径配置（空字符串表示由消费方动态推导）──────────────────────────────
    db_path: str = ""
    workflows_root: str = ""
    skills_root: str = ""
    prompts_root: str = ""

    # ── 默认工作流输入 ────────────────────────────────────────────────────────
    default_workflow_inputs: dict[str, Any] = {
        "repo_path": "",
        "readme_path": "README.md",
        "output_path": "output.txt",
        "retry_count": 0,
        "max_retries": 3,
    }


# 模块级单例，全项目通过 `from config.settings import settings` 访问
settings = Settings()
