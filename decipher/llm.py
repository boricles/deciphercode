"""LLM client wrapper for OpenAI-compatible APIs."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from openai import OpenAI

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_API_BASE = "http://localhost:11434/v1"  # Ollama default
DEFAULT_MODEL = "llama3"
MAX_RETRIES = 3


@dataclass
class LLMConfig:
    """Configuration for the LLM client, sourced from env vars or explicit values."""

    api_base: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.api_base = self.api_base or os.getenv("DECIPHER_API_BASE", DEFAULT_API_BASE)
        self.api_key = self.api_key or os.getenv("DECIPHER_API_KEY", "ollama")
        self.model = self.model or os.getenv("DECIPHER_MODEL", DEFAULT_MODEL)


class LLMClient:
    """Thin wrapper around any OpenAI-compatible API."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._client = OpenAI(
            base_url=self.config.api_base,
            api_key=self.config.api_key,
            max_retries=MAX_RETRIES,
            default_headers=self.config.extra_headers or None,
        )
        logger.info(
            "LLM client initialised: base=%s model=%s",
            self.config.api_base,
            self.config.model,
        )

    def chat(
        self,
        prompt: str,
        system: str = "You are a senior software engineer who analyzes codebases.",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a single prompt and return the assistant's reply."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        return self._complete(messages, temperature, max_tokens)

    def chat_with_history(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a full message history and return the assistant's reply."""
        return self._complete(messages, temperature, max_tokens)

    def _complete(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        logger.debug("Sending %d messages to %s", len(messages), self.config.model)

        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temp,
            max_tokens=tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug("Received %d chars", len(content))
        return content
