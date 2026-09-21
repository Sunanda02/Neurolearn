"""
backend/ml/llm_providers.py

Provider-agnostic LLM abstraction used by ml/question_generator.py.

    Assessment (routers/assessment.py)
        ↓
    question_generator.generate_questions(...)
        ↓
    BaseLLMProvider.generate(prompt)          ← question_generator.py only
        ↓                                        ever depends on this
    OllamaProvider (today's configured provider)
        ↓
    Configured model (LLM_MODEL, opaque string)

Everything provider- and connection-specific (which HTTP API to call, how
to talk to it, how to detect "model not found" vs "server unreachable")
lives in this file. question_generator.py never imports `requests`,
constructs a URL, or knows the provider is Ollama.

Adding a future provider (OpenAI-compatible API, Azure, Anthropic, a
different self-hosted server) means adding one more BaseLLMProvider
subclass here and one branch in get_llm_provider() — nothing upstream
(question_generator.py, assessment.py, MCRF, LEGACY) changes.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import requests
from loguru import logger

from config.llm_config import LLM_CONFIG


# ── Errors ────────────────────────────────────────────────────────────────
# All provider failures are subclasses of LLMProviderError. Callers
# (question_generator.py, and ultimately assessment.py) must let these
# propagate into a clear backend error — never treat one as "no question
# generated, fall back to something else."

class LLMProviderError(Exception):
    """Base class for any LLM-provider failure."""


class LLMConnectionError(LLMProviderError):
    """Could not reach the configured LLM_BASE_URL at all."""


class LLMTimeoutError(LLMProviderError):
    """The provider did not respond within LLM_TIMEOUT_SECONDS."""


class LLMModelUnavailableError(LLMProviderError):
    """The configured LLM_MODEL is not available on the provider."""


class LLMResponseParseError(LLMProviderError):
    """The provider responded, but not with a body we can use."""


# ── Abstraction ──────────────────────────────────────────────────────────

class BaseLLMProvider(ABC):
    """Minimal interface every provider must implement. Question-generation
    logic, retries, and content validation all live in
    ml/question_generator.py and depend only on this method.
    """

    @abstractmethod
    def generate(self, prompt: str, *, temperature: float = 0.4, json_mode: bool = False) -> str:
        """Return the raw text completion for `prompt`.

        Must raise an LLMProviderError subclass on any failure (connection,
        timeout, missing model, unparseable response) — never return a
        placeholder, partial string, or empty string on failure.

        `json_mode`: when True, ask the provider to constrain output to
        valid JSON if it supports that (structural, not model-specific —
        e.g. Ollama's `format: "json"`). Callers must still validate the
        parsed content themselves; this is a reliability aid, not a
        guarantee any particular model followed the schema.
        """
        raise NotImplementedError


# ── Ollama implementation ───────────────────────────────────────────────

class OllamaProvider(BaseLLMProvider):
    """Calls Ollama's HTTP API (`POST {base_url}/api/generate`),
    non-streaming.

    `base_url` and `model` are both plain configuration — this class
    contains no logic keyed on which model is configured, so changing
    LLM_MODEL to any other model already pulled in Ollama needs no code
    change here. `base_url` is never assumed to be localhost beyond the
    config default, so pointing it at a remote/hosted Ollama server needs
    no code change either — only .env.
    """

    def __init__(self, base_url: str, model: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str, *, temperature: float = 0.4, json_mode: bool = False) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = requests.post(url, json=payload, timeout=self.timeout_seconds)
        except requests.exceptions.Timeout as exc:
            raise LLMTimeoutError(
                f"Ollama request to {self.base_url} timed out after {self.timeout_seconds}s"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise LLMConnectionError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMConnectionError(f"Ollama request failed: {exc}") from exc

        if response.status_code == 404:
            raise LLMModelUnavailableError(
                f"Model '{self.model}' is not available on Ollama at {self.base_url} "
                f"(pull it first with: ollama pull {self.model})"
            )
        if response.status_code != 200:
            raise LLMProviderError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMResponseParseError(f"Ollama response body was not valid JSON: {exc}") from exc

        text = data.get("response")
        if not isinstance(text, str) or not text.strip():
            raise LLMResponseParseError("Ollama response had no non-empty 'response' field")
        return text


# ── Factory ──────────────────────────────────────────────────────────────

def get_llm_provider() -> BaseLLMProvider:
    """The ONLY place in the codebase that switches on LLM_PROVIDER.

    Adding a new provider later (OpenAIProvider, AzureProvider,
    AnthropicProvider, a hosted-Ollama variant, etc.) means writing the
    class above and adding one `elif` branch here — nothing else needs to
    change, including question_generator.py and assessment.py.
    """
    provider_name = LLM_CONFIG.provider
    if provider_name == "ollama":
        logger.info(f"LLM provider: ollama | LLM model: {LLM_CONFIG.model} | base_url: {LLM_CONFIG.base_url}")
        return OllamaProvider(
            base_url=LLM_CONFIG.base_url,
            model=LLM_CONFIG.model,
            timeout_seconds=LLM_CONFIG.timeout_seconds,
        )
    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider_name}'. Supported providers: ollama."
    )