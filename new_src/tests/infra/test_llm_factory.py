"""LLMClientRegistry 客户端缓存单元测试。"""
from unittest.mock import MagicMock, patch

import pytest

from agent.infra.llm_factory import LLMClientRegistry, resolve_llm_provider, resolve_model_name


# ── LLMClientRegistry 缓存测试 ────────────────────────────────────────────────

class TestLLMClientRegistry:
    """验证 LLMClientRegistry 的单例模式和缓存逻辑。"""

    def setup_method(self):
        """每个测试前重置单例和缓存，确保测试隔离。"""
        LLMClientRegistry.reset()

    def test_instance_returns_singleton(self):
        """instance() 应始终返回同一对象。"""
        r1 = LLMClientRegistry.instance()
        r2 = LLMClientRegistry.instance()
        assert r1 is r2

    def test_get_or_create_returns_same_instance_for_same_config(self):
        """相同配置参数应返回同一客户端实例（缓存命中）。"""
        fake_client = MagicMock(name="llm_client")

        with patch("agent.infra.llm_factory.build_chat_model", return_value=fake_client) as mock_build:
            registry = LLMClientRegistry.instance()
            client1 = registry.get_or_create(
                provider="gemini", model="flash", temperature=0.0, json_mode=False
            )
            client2 = registry.get_or_create(
                provider="gemini", model="flash", temperature=0.0, json_mode=False
            )

        # build_chat_model 只应被调用一次
        assert mock_build.call_count == 1
        assert client1 is client2
        assert client1 is fake_client

    def test_get_or_create_different_temperature_creates_new_client(self):
        """不同 temperature 应创建不同的客户端实例。"""
        fake1 = MagicMock(name="client_t0")
        fake2 = MagicMock(name="client_t1")

        with patch("agent.infra.llm_factory.build_chat_model", side_effect=[fake1, fake2]):
            registry = LLMClientRegistry.instance()
            client1 = registry.get_or_create("gemini", "flash", 0.0, False)
            client2 = registry.get_or_create("gemini", "flash", 0.5, False)

        assert client1 is not client2
        assert client1 is fake1
        assert client2 is fake2

    def test_get_or_create_different_json_mode_creates_new_client(self):
        """不同 json_mode 应创建不同的客户端实例。"""
        fake1 = MagicMock(name="client_no_json")
        fake2 = MagicMock(name="client_json")

        with patch("agent.infra.llm_factory.build_chat_model", side_effect=[fake1, fake2]):
            registry = LLMClientRegistry.instance()
            client1 = registry.get_or_create("gemini", "flash", 0.0, False)
            client2 = registry.get_or_create("gemini", "flash", 0.0, True)

        assert client1 is not client2

    def test_get_or_create_different_provider_creates_new_client(self):
        """不同提供商应创建不同的客户端实例。"""
        fake1 = MagicMock(name="gemini_client")
        fake2 = MagicMock(name="openai_client")

        with patch("agent.infra.llm_factory.build_chat_model", side_effect=[fake1, fake2]):
            registry = LLMClientRegistry.instance()
            client1 = registry.get_or_create("gemini", "flash", 0.0, False)
            client2 = registry.get_or_create("openai", "gpt-4o", 0.0, False)

        assert client1 is not client2

    def test_clear_empties_cache(self):
        """clear() 后，相同配置应重新调用 build_chat_model。"""
        fake = MagicMock(name="client")

        with patch("agent.infra.llm_factory.build_chat_model", return_value=fake) as mock_build:
            registry = LLMClientRegistry.instance()
            registry.get_or_create("gemini", "flash", 0.0, False)
            registry.clear()
            registry.get_or_create("gemini", "flash", 0.0, False)

        assert mock_build.call_count == 2

    def test_reset_creates_new_singleton(self):
        """reset() 后，instance() 应返回新的单例对象。"""
        r1 = LLMClientRegistry.instance()
        LLMClientRegistry.reset()
        r2 = LLMClientRegistry.instance()
        assert r1 is not r2

    def test_multiple_configs_are_cached_independently(self):
        """多个不同配置应各自缓存，互不干扰。"""
        clients = {
            ("gemini", "flash", 0.0, False): MagicMock(),
            ("openai", "gpt-4o", 0.1, False): MagicMock(),
            ("deepseek", "deepseek-chat", 0.0, True): MagicMock(),
        }

        def build_side_effect(model_name, temperature):
            for (p, m, t, j), client in clients.items():
                if m == model_name and t == temperature:
                    return client
            return MagicMock()

        with patch("agent.infra.llm_factory.build_chat_model", side_effect=build_side_effect):
            registry = LLMClientRegistry.instance()
            for (p, m, t, j) in clients:
                registry.get_or_create(p, m, t, j)

            # 再次获取，应命中缓存
            with patch("agent.infra.llm_factory.build_chat_model") as mock_build:
                for (p, m, t, j) in clients:
                    registry.get_or_create(p, m, t, j)
                assert mock_build.call_count == 0


# ── resolve_llm_provider / resolve_model_name 测试 ────────────────────────────

class TestResolveHelpers:
    def test_resolve_model_name_explicit_override(self):
        """传入显式 model_name 时，直接返回该名称。"""
        result = resolve_model_name("my-custom-model")
        assert result == "my-custom-model"

    def test_resolve_llm_provider_returns_string(self):
        """resolve_llm_provider() 应返回非空字符串。"""
        provider = resolve_llm_provider()
        assert isinstance(provider, str)
        assert len(provider) > 0
