"""
LLM Client Abstraction for Mindnotes
────────────────────────────────────
Provider-agnostic LLM client with timeout and retry support.
Supports Anthropic, OpenAI, DeepSeek, and Gemini with direct HTTP fallbacks.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from mindnotes.config import load_config

# Ensure .env is loaded
load_config()

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Normalised LLM response across providers."""
    raw: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0


class LLMError(Exception):
    """Base exception for LLM call failures."""
    pass


class LLMTimeoutError(LLMError):
    """LLM call exceeded configured timeout."""
    pass


class LLMClient:
    """Provider-agnostic LLM client."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
    ):
        load_config()
        self._provider = provider or self._detect_provider()
        self._model = model
        self._default_timeout = timeout_seconds

    @staticmethod
    def _detect_provider() -> str:
        """Detect first available provider from environment."""
        if os.getenv("DEEPSEEK_API_KEY"):
            return "deepseek"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.getenv("GEMINI_API_KEY"):
            return "gemini"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        raise LLMError(
            "No LLM API key found. Please set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
            "GEMINI_API_KEY, or DEEPSEEK_API_KEY in ~/Mindnotes/.env"
        )

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        if self._model:
            return self._model
        return {
            "anthropic": "claude-3-5-sonnet-latest",
            "openai": "gpt-4o",
            "deepseek": "deepseek-chat",
            "gemini": "gemini-2.0-flash",
        }.get(self._provider, "unknown")

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2000,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        """Send completion request to configured LLM provider."""
        timeout = timeout_seconds if timeout_seconds is not None else self._default_timeout
        provider = self._provider

        if provider == "deepseek":
            return self._call_deepseek(system_prompt, user_message, max_tokens, timeout)
        elif provider == "anthropic":
            return self._call_anthropic(system_prompt, user_message, max_tokens, timeout)
        elif provider == "openai":
            return self._call_openai(system_prompt, user_message, max_tokens, timeout)
        elif provider == "gemini":
            return self._call_gemini(system_prompt, user_message, max_tokens, timeout)
        else:
            raise LLMError(f"Unsupported provider: {provider}")

    def _call_deepseek(
        self, system: str, user: str, max_tokens: int, timeout: float
    ) -> LLMResponse:
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        start = time.monotonic()

        # Try openai SDK if installed, otherwise direct HTTP via requests
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                timeout=timeout,
            )
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            return LLMResponse(
                raw=response.choices[0].message.content or "",
                provider="deepseek",
                model=self.model,
                latency_ms=latency_ms,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            )
        except ImportError:
            import requests
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=timeout)
                res.raise_for_status()
                data = res.json()
                raw_text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                latency_ms = int((time.monotonic() - start) * 1000)
                return LLMResponse(
                    raw=raw_text,
                    provider="deepseek",
                    model=self.model,
                    latency_ms=latency_ms,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                )
            except Exception as e:
                if "timeout" in str(e).lower():
                    raise LLMTimeoutError(f"DeepSeek call timed out: {e}") from e
                raise LLMError(f"DeepSeek call failed: {e}") from e

    def _call_anthropic(
        self, system: str, user: str, max_tokens: int, timeout: float
    ) -> LLMResponse:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        start = time.monotonic()
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            return LLMResponse(
                raw=response.content[0].text,
                provider="anthropic",
                model=self.model,
                latency_ms=latency_ms,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
        except ImportError:
            import requests
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            res = requests.post(url, headers=headers, json=payload, timeout=timeout)
            res.raise_for_status()
            data = res.json()
            latency_ms = int((time.monotonic() - start) * 1000)
            return LLMResponse(
                raw=data["content"][0]["text"],
                provider="anthropic",
                model=self.model,
                latency_ms=latency_ms,
            )
        except Exception as e:
            if "timeout" in str(e).lower():
                raise LLMTimeoutError(f"Anthropic call timed out: {e}") from e
            raise LLMError(f"Anthropic call failed: {e}") from e

    def _call_openai(
        self, system: str, user: str, max_tokens: int, timeout: float
    ) -> LLMResponse:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        start = time.monotonic()
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=timeout)
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            return LLMResponse(
                raw=response.choices[0].message.content or "",
                provider="openai",
                model=self.model,
                latency_ms=latency_ms,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            )
        except ImportError:
            import requests
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=timeout)
            res.raise_for_status()
            data = res.json()
            latency_ms = int((time.monotonic() - start) * 1000)
            return LLMResponse(
                raw=data["choices"][0]["message"]["content"],
                provider="openai",
                model=self.model,
                latency_ms=latency_ms,
            )
        except Exception as e:
            if "timeout" in str(e).lower():
                raise LLMTimeoutError(f"OpenAI call timed out: {e}") from e
            raise LLMError(f"OpenAI call failed: {e}") from e

    def _call_gemini(
        self, system: str, user: str, max_tokens: int, timeout: float
    ) -> LLMResponse:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        start = time.monotonic()
        try:
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}],
                "generationConfig": {"maxOutputTokens": max_tokens},
            }
            res = requests.post(url, json=payload, timeout=timeout)
            res.raise_for_status()
            data = res.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            latency_ms = int((time.monotonic() - start) * 1000)
            return LLMResponse(
                raw=raw_text,
                provider="gemini",
                model=self.model,
                latency_ms=latency_ms,
            )
        except Exception as e:
            if "timeout" in str(e).lower():
                raise LLMTimeoutError(f"Gemini call timed out: {e}") from e
            raise LLMError(f"Gemini call failed: {e}") from e
