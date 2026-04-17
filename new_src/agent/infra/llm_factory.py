"""LLM 工厂与客户端注册中心。

提供两套 API：
1. 函数式工厂（向下兼容）：resolve_llm_provider / resolve_model_name /
   build_chat_model / build_structured_output_model
2. LLMClientRegistry 单例：按 (provider, model, temperature, json_mode) 缓存实例，
   避免每次 skill 调用都创建新客户端。

配置统一从 config.settings.settings 对象读取，不直接访问 os.environ。
"""
from __future__ import annotations

import logging
import os
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


# ── 函数式工厂 ────────────────────────────────────────────────────────────────

def resolve_llm_provider() -> str:
    """返回当前配置的 LLM 提供商（小写）。"""
    return settings.llm_provider


def resolve_model_name(model_name: str | None = None) -> str:
    """解析最终使用的模型名称。

    优先级：参数 > settings.llm_model > 提供商默认模型。
    """
    if model_name:
        return model_name
    if settings.llm_model:
        return settings.llm_model
    provider = resolve_llm_provider()
    if provider in {"gemini", "google"}:
        return settings.gemini_model
    if provider == "deepseek":
        return settings.deepseek_model
    if provider == "openai":
        return settings.openai_model
    return settings.gemini_model


def build_chat_model(model_name: str | None = None, temperature: float = 0.0):
    """构建 LangChain 聊天模型客户端。

    根据 settings.llm_provider 选择对应的 LangChain 实现。
    """
    provider = resolve_llm_provider()
    resolved_model = resolve_model_name(model_name)

    if provider in {"gemini", "google"}:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError(
                "LLM_PROVIDER=gemini 需要安装 langchain-google-genai。"
            ) from exc
        api_key = settings.gemini_api_key
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        return ChatGoogleGenerativeAI(model=resolved_model, temperature=temperature)

    if provider in {"deepseek", "openai"}:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "LLM_PROVIDER=deepseek/openai 需要安装 langchain-openai。"
            ) from exc
        if provider == "deepseek":
            api_key = settings.deepseek_api_key
            base_url = settings.deepseek_base_url
        else:
            api_key = settings.openai_api_key
            base_url = settings.openai_base_url

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "temperature": temperature,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def resolve_structured_output_kwargs(provider: str | None = None) -> dict[str, Any]:
    """返回提供商专属的 with_structured_output() kwargs。"""
    current = (provider or resolve_llm_provider()).strip().lower()
    if current == "deepseek":
        return {"method": "function_calling"}
    return {}


def build_structured_output_model(llm: Any, schema: Any, provider: str | None = None) -> Any:
    """构建结构化输出 Runnable（兼容各提供商差异）。"""
    kwargs = resolve_structured_output_kwargs(provider)
    if kwargs:
        return llm.with_structured_output(schema, **kwargs)
    return llm.with_structured_output(schema)


# ── 客户端注册中心 ────────────────────────────────────────────────────────────

class LLMClientRegistry:
    """LLM 客户端单例注册中心。

    按 (provider, model, temperature, json_mode) 四元组缓存客户端实例，
    相同配置的请求复用同一客户端，避免重复创建开销。

    用法::

        client = LLMClientRegistry.instance().get_or_create(
            provider="gemini",
            model="gemini-flash",
            temperature=0.0,
            json_mode=False,
        )
    """

    _instance: LLMClientRegistry | None = None

    def __init__(self) -> None:
        self._cache: dict[tuple, Any] = {}

    @classmethod
    def instance(cls) -> LLMClientRegistry:
        """返回全局单例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_or_create(
        self,
        provider: str,
        model: str,
        temperature: float,
        json_mode: bool = False,
    ) -> Any:
        """获取或创建 LLM 客户端。

        Args:
            provider:    提供商标识，如 "gemini"、"deepseek"、"openai"。
            model:       模型名称。
            temperature: 采样温度。
            json_mode:   是否启用 JSON 输出模式（作为缓存键一部分）。

        Returns:
            LangChain 聊天模型实例（可复用）。
        """
        key = (provider, model, temperature, json_mode)
        if key not in self._cache:
            logger.debug(
                "LLMClientRegistry: 创建新客户端 provider=%s model=%s temperature=%s json_mode=%s",
                provider, model, temperature, json_mode,
            )
            self._cache[key] = build_chat_model(model_name=model, temperature=temperature)
        return self._cache[key]

    def clear(self) -> None:
        """清空客户端缓存（主要用于测试隔离）。"""
        self._cache.clear()

    @classmethod
    def reset(cls) -> None:
        """重置单例（主要用于测试隔离）。"""
        cls._instance = None
