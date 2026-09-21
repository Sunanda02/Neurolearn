"""
backend/config/llm_config.py

Provider-agnostic LLM configuration for question generation, following the
same pattern as config/crs_config.py: nothing in ml/llm_providers.py or
ml/question_generator.py should read an LLM_* environment variable or
hard-code a provider name, model name, or host directly — it should come
from this one module, so a deployment can switch provider, model, or host
by editing .env alone, with no Python code changes.

    LLM_PROVIDER=ollama                        # which provider to use
    LLM_MODEL=qwen2.5:7b                        # opaque to the provider code
    LLM_BASE_URL=http://localhost:11434         # never assumed elsewhere
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Defensive: main.py already calls load_dotenv() before importing routers
# (which import this module transitively), but this module may also be
# imported directly (e.g. in tests or scripts) without that happening first.
load_dotenv()


@dataclass(frozen=True)
class LLMConfig:
    # Which BaseLLMProvider implementation to use (see ml/llm_providers.py).
    # "ollama" is the only one implemented today; the factory there is the
    # single place that switches on this value.
    provider: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

    # Opaque to every provider implementation — never branched on by name
    # anywhere in the codebase. Changing this alone (e.g. to any other
    # model already pulled in Ollama) requires no code change.
    model: str = os.getenv("LLM_MODEL", "qwen2.5:7b").strip()

    # Where the provider's server lives. Defaults to local Ollama for
    # development; pointing this at a remote/hosted Ollama server later
    # requires no code change, only editing .env.
    base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434").rstrip("/")

    # Per-request timeout, in seconds, for a single generation call.
    timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    # Bounded retry budget for producing ONE valid question (covers both
    # transient provider errors and content-validation rejections). Kept
    # small deliberately — this is not the old 20x FLAN-T5 retry loop.
    max_generation_attempts: int = int(os.getenv("LLM_MAX_ATTEMPTS", "3"))


# Module-level singleton — import this, don't re-instantiate.
LLM_CONFIG = LLMConfig()