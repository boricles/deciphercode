"""Tests for decipher.llm."""

import os
from unittest.mock import MagicMock, patch

import pytest

from decipher.llm import (
    PROVIDER_ANTHROPIC,
    PROVIDER_AZURE,
    PROVIDER_OPENAI,
    LLMClient,
    LLMConfig,
    _detect_provider,
)


# -- provider detection ------------------------------------------------------


class TestDetectProvider:
    def test_default_is_openai(self):
        assert _detect_provider("http://localhost:11434/v1", "") == PROVIDER_OPENAI

    def test_azure_openai_domain(self):
        assert _detect_provider("https://myres.openai.azure.com/v1", "") == PROVIDER_AZURE

    def test_azure_cognitive_domain(self):
        url = "https://myres.cognitiveservices.azure.com"
        assert _detect_provider(url, "") == PROVIDER_AZURE

    def test_explicit_anthropic(self):
        assert _detect_provider("http://localhost:8080", "anthropic") == PROVIDER_ANTHROPIC

    def test_explicit_azure(self):
        assert _detect_provider("http://custom-proxy.local", "azure") == PROVIDER_AZURE

    def test_explicit_openai(self):
        assert _detect_provider("http://custom-proxy.local", "openai") == PROVIDER_OPENAI

    def test_explicit_overrides_domain(self):
        assert (
            _detect_provider("https://myres.openai.azure.com", "openai") == PROVIDER_OPENAI
        )

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            _detect_provider("http://localhost", "bedrock")


# -- config ------------------------------------------------------------------


class TestLLMConfig:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = LLMConfig()
            assert "localhost" in config.api_base
            assert config.model == "llama3"
            assert config.provider == PROVIDER_OPENAI

    def test_env_vars(self):
        env = {
            "DECIPHER_API_BASE": "https://api.example.com/v1",
            "DECIPHER_API_KEY": "sk-test-123",
            "DECIPHER_MODEL": "gpt-4o",
        }
        with patch.dict(os.environ, env, clear=False):
            config = LLMConfig()
            assert config.api_base == "https://api.example.com/v1"
            assert config.api_key == "sk-test-123"
            assert config.model == "gpt-4o"
            assert config.provider == PROVIDER_OPENAI

    def test_explicit_overrides_env(self):
        env = {"DECIPHER_MODEL": "gpt-4o"}
        with patch.dict(os.environ, env, clear=False):
            config = LLMConfig(model="claude-3")
            assert config.model == "claude-3"

    def test_azure_auto_detected(self):
        config = LLMConfig(
            api_base="https://myres.openai.azure.com",
            api_key="azure-key",
        )
        assert config.provider == PROVIDER_AZURE

    def test_anthropic_via_env(self):
        env = {"DECIPHER_API_PROVIDER": "anthropic"}
        with patch.dict(os.environ, env, clear=False):
            config = LLMConfig(api_base="http://localhost:8080", api_key="sk-ant-xxx")
            assert config.provider == PROVIDER_ANTHROPIC

    def test_api_version_default(self):
        config = LLMConfig(api_base="https://x.openai.azure.com", api_key="k")
        assert config.api_version == "2024-10-21"

    def test_api_version_from_env(self):
        env = {"DECIPHER_API_VERSION": "2025-01-01"}
        with patch.dict(os.environ, env, clear=False):
            config = LLMConfig()
            assert config.api_version == "2025-01-01"


# -- helpers for mocking -----------------------------------------------------


def _mock_openai_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


def _mock_anthropic_response(text: str) -> MagicMock:
    resp = MagicMock()
    content_block = MagicMock()
    content_block.text = text
    resp.content = [content_block]
    return resp


# -- OpenAI client -----------------------------------------------------------


class TestLLMClientOpenAI:
    def test_chat(self):
        config = LLMConfig(api_base="http://fake", api_key="test", model="test-model")

        with patch("decipher.llm.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            mock_client.chat.completions.create.return_value = _mock_openai_response(
                "Hello from LLM"
            )

            client = LLMClient(config)
            result = client.chat("Test prompt")

            assert result == "Hello from LLM"
            mock_client.chat.completions.create.assert_called_once()

    def test_chat_with_history(self):
        config = LLMConfig(api_base="http://fake", api_key="test", model="test-model")

        with patch("decipher.llm.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            mock_client.chat.completions.create.return_value = _mock_openai_response("Response")

            client = LLMClient(config)
            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hi"},
            ]
            result = client.chat_with_history(messages)

            assert result == "Response"


# -- Azure client ------------------------------------------------------------


class TestLLMClientAzure:
    def test_azure_init_strips_suffix(self):
        config = LLMConfig(
            api_base="https://myres.openai.azure.com/openai/deployments/gpt4/v1",
            api_key="azure-key",
            model="gpt4",
        )

        with patch("decipher.llm.AzureOpenAI") as MockAzure:
            MockAzure.return_value = MagicMock()
            LLMClient(config)

            call_kwargs = MockAzure.call_args[1]
            assert call_kwargs["azure_endpoint"] == "https://myres.openai.azure.com"
            assert call_kwargs["api_version"] == "2024-10-21"

    def test_azure_missing_key_raises(self):
        config = LLMConfig(
            api_base="https://myres.openai.azure.com",
            api_key="ollama",
            model="gpt4",
        )
        with pytest.raises(ValueError, match="Azure OpenAI requires an API key"):
            LLMClient(config)

    def test_azure_chat(self):
        config = LLMConfig(
            api_base="https://myres.openai.azure.com",
            api_key="azure-key",
            model="gpt4",
        )

        with patch("decipher.llm.AzureOpenAI") as MockAzure:
            mock_client = MagicMock()
            MockAzure.return_value = mock_client
            mock_client.chat.completions.create.return_value = _mock_openai_response(
                "Azure response"
            )

            client = LLMClient(config)
            result = client.chat("Test")

            assert result == "Azure response"


# -- Anthropic client --------------------------------------------------------


class TestLLMClientAnthropic:
    def test_anthropic_init(self):
        config = LLMConfig(
            api_base="http://localhost:8080",
            api_key="sk-ant-xxx",
            model="claude-opus-4-6",
            provider="anthropic",
        )

        with patch("decipher.llm.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = MagicMock()
            LLMClient(config)

            call_kwargs = MockAnthropic.call_args[1]
            assert call_kwargs["api_key"] == "sk-ant-xxx"
            assert call_kwargs["base_url"] == "http://localhost:8080"

    def test_anthropic_chat_separates_system(self):
        config = LLMConfig(
            api_base="http://localhost:8080",
            api_key="sk-ant-xxx",
            model="claude-opus-4-6",
            provider="anthropic",
        )

        with patch("decipher.llm.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_anthropic_response(
                "Anthropic response"
            )

            client = LLMClient(config)
            result = client.chat("Analyze this code", system="You are a code reviewer.")

            assert result == "Anthropic response"

            create_kwargs = mock_client.messages.create.call_args[1]
            assert create_kwargs["system"] == "You are a code reviewer."
            for msg in create_kwargs["messages"]:
                assert msg["role"] != "system"

    def test_anthropic_chat_with_history(self):
        config = LLMConfig(
            api_base="http://localhost:8080",
            api_key="sk-ant-xxx",
            model="claude-opus-4-6",
            provider="anthropic",
        )

        with patch("decipher.llm.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_anthropic_response(
                "History response"
            )

            client = LLMClient(config)
            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
                {"role": "user", "content": "What is this?"},
            ]
            result = client.chat_with_history(messages)

            assert result == "History response"

            create_kwargs = mock_client.messages.create.call_args[1]
            assert create_kwargs["system"] == "You are helpful."
            assert len(create_kwargs["messages"]) == 3
