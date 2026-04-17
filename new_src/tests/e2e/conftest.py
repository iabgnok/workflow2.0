"""E2E 测试公共 fixture：加载 .env、重置 LLM 客户端缓存。"""
from __future__ import annotations

import os
import sys

import pytest
from dotenv import dotenv_values, load_dotenv

# 将 new_src 加入 sys.path
_new_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _new_src not in sys.path:
    sys.path.insert(0, _new_src)

# 项目根目录（new_src 的父级）
_project_root = os.path.abspath(os.path.join(_new_src, ".."))
_env_path = os.path.join(_project_root, ".env")


def has_deepseek_api_key() -> bool:
    """同时检查当前环境与项目根 .env 中的 DEEPSEEK_API_KEY。"""
    if (os.environ.get("DEEPSEEK_API_KEY") or "").strip():
        return True
    env_file_values = dotenv_values(_env_path)
    return bool((env_file_values.get("DEEPSEEK_API_KEY") or "").strip())


@pytest.fixture(scope="session", autouse=True)
def load_e2e_env_once():
    """仅在 e2e 用例真正执行时加载 .env，避免污染非 e2e 测试。"""
    load_dotenv(_env_path, override=True)
    yield


@pytest.fixture(scope="session", autouse=True)
def force_utf8_stdio_once():
    """统一测试输出编码为 UTF-8，避免 Windows 控制台乱码。"""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    yield


@pytest.fixture(autouse=True)
def reset_llm_client_registry():
    """每个测试后重置 LLM 客户端缓存，避免跨测试污染。"""
    yield
    from agent.infra.llm_factory import LLMClientRegistry
    LLMClientRegistry.reset()
