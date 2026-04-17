"""Tests for decipher.llm."""

import os
from unittest.mock import MagicMock, patch

from decipher.llm import LLMClient, LLMConfig


class TestLLMConfig:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = LLMConfig()
            assert "localhost" in config.api_base
            assert config.model == "llama3"

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

    def test_explicit_overrides_env(self):
        env = {"DECIPHER_MODEL": "gpt-4o"}
        with patch.dict(os.environ, env, clear=False):
            config = LLMConfig(model="claude-3")
            assert config.model == "claude-3"


class TestLLMClient:
    def test_chat(self):
        config = LLMConfig(api_base="http://fake", api_key="test", model="test-model")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from LLM"

        with patch("decipher.llm.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            client = LLMClient(config)
            result = client.chat("Test prompt")

            assert result == "Hello from LLM"
            mock_client.chat.completions.create.assert_called_once()

    def test_chat_with_history(self):
        config = LLMConfig(api_base="http://fake", api_key="test", model="test-model")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch("decipher.llm.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            client = LLMClient(config)
            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hi"},
            ]
            result = client.chat_with_history(messages)

            assert result == "Response"
