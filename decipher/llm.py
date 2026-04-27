"""LLM client wrapper supporting OpenAI, Azure OpenAI, and Anthropic APIs."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from openai import AzureOpenAI, OpenAI

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_API_BASE = "http://localhost:11434/v1"  # Ollama default
DEFAULT_MODEL = "llama3"
DEFAULT_AZURE_API_VERSION = "2024-10-21"
MAX_RETRIES = 3

# Provider constants
PROVIDER_OPENAI = "openai"
PROVIDER_AZURE = "azure"
PROVIDER_ANTHROPIC = "anthropic"

_AZURE_DOMAINS = ("openai.azure.com", "cognitiveservices.azure.com")


def _detect_provider(api_base: str, explicit_provider: str) -> str:
    """Determine which provider to use based on config.

    Priority:
      1. Explicit DECIPHER_API_PROVIDER env var / explicit_provider arg
      2. Azure domain detection in the base URL
      3. Default to standard OpenAI client
    """
    if explicit_provider:
        normalised = explicit_provider.strip().lower()
        if normalised in (PROVIDER_OPENAI, PROVIDER_AZURE, PROVIDER_ANTHROPIC):
            return normalised
        raise ValueError(
            f"Unknown provider '{explicit_provider}'. Supported values: openai, azure, anthropic"
        )

    for domain in _AZURE_DOMAINS:
        if domain in api_base:
            return PROVIDER_AZURE

    return PROVIDER_OPENAI


@dataclass
class LLMConfig:
    """Configuration for the LLM client, sourced from env vars or explicit values."""

    api_base: str = ""
    api_key: str = ""
    model: str = ""
    provider: str = ""
    api_version: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.api_base = self.api_base or os.getenv("DECIPHER_API_BASE", DEFAULT_API_BASE)
        self.api_key = self.api_key or os.getenv("DECIPHER_API_KEY", "ollama")
        self.model = self.model or os.getenv("DECIPHER_MODEL", DEFAULT_MODEL)
        self.api_version = self.api_version or os.getenv(
            "DECIPHER_API_VERSION", DEFAULT_AZURE_API_VERSION
        )

        explicit = self.provider or os.getenv("DECIPHER_API_PROVIDER", "")
        self.provider = _detect_provider(self.api_base, explicit)


class LLMClient:
    """Unified client that delegates to OpenAI, Azure OpenAI, or Anthropic."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._provider = self.config.provider
        self._init_client()

        logger.info(
            "LLM client initialised: provider=%s base=%s model=%s",
            self._provider,
            self.config.api_base,
            self.config.model,
        )

    def _init_client(self) -> None:
        if self._provider == PROVIDER_AZURE:
            self._init_azure()
        elif self._provider == PROVIDER_ANTHROPIC:
            self._init_anthropic()
        else:
            self._init_openai()

    def _init_openai(self) -> None:
        self._openai = OpenAI(
            base_url=self.config.api_base,
            api_key=self.config.api_key,
            max_retries=MAX_RETRIES,
            default_headers=self.config.extra_headers or None,
        )

    def _init_azure(self) -> None:
        endpoint = self.config.api_base.rstrip("/")
        # Strip /openai/deployments/... suffix if the user included it;
        # the AzureOpenAI client builds the full URL itself.
        for marker in ("/openai/deployments", "/openai"):
            idx = endpoint.find(marker)
            if idx != -1:
                endpoint = endpoint[:idx]
                break

        if not self.config.api_key or self.config.api_key == "ollama":
            raise ValueError(
                "Azure OpenAI requires an API key. Set DECIPHER_API_KEY to your Azure key."
            )

        self._openai = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=self.config.api_key,
            api_version=self.config.api_version,
            max_retries=MAX_RETRIES,
            default_headers=self.config.extra_headers or None,
        )

    def _init_anthropic(self) -> None:
        if Anthropic is None:
            raise ImportError(
                "Anthropic support requires the 'anthropic' package. "
                "Install it with: pip install anthropic"
            )

        kwargs: dict = {"api_key": self.config.api_key, "max_retries": MAX_RETRIES}
        if self.config.api_base and self.config.api_base != DEFAULT_API_BASE:
            kwargs["base_url"] = self.config.api_base
        if self.config.extra_headers:
            kwargs["default_headers"] = self.config.extra_headers

        self._anthropic = Anthropic(**kwargs)

    # -- public API (unchanged interface) ------------------------------------

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

    # -- dispatch ------------------------------------------------------------

    def _complete(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        if self._provider == PROVIDER_ANTHROPIC:
            return self._complete_anthropic(messages, temperature, max_tokens)
        return self._complete_openai(messages, temperature, max_tokens)

    def _complete_openai(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        """Complete via OpenAI or Azure OpenAI (both use the same SDK interface)."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        logger.debug(
            "Sending %d messages to %s [%s]", len(messages), self.config.model, self._provider
        )

        response = self._openai.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temp,
            max_tokens=tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug("Received %d chars", len(content))
        return content

    def _complete_anthropic(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        """Complete via Anthropic Messages API."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        # Anthropic expects system as a separate parameter, not in messages
        system_text = ""
        filtered: list[dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                filtered.append(msg)

        if not filtered:
            filtered = [{"role": "user", "content": "Hello"}]

        logger.debug("Sending %d messages to %s [anthropic]", len(filtered), self.config.model)

        kwargs: dict = {
            "model": self.config.model,
            "messages": filtered,
            "max_tokens": tokens,
            "temperature": temp,
        }
        if system_text:
            kwargs["system"] = system_text

        response = self._anthropic.messages.create(**kwargs)
        content = response.content[0].text if response.content else ""
        logger.debug("Received %d chars", len(content))
        return content
