from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import LLMError, LLMUnavailableError

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """Synchronous DeepSeek API client with timeout and retry."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.deepseek_base_url.rstrip("/")
        self._api_key = settings.deepseek_api_key
        self._model = settings.deepseek_model
        self._timeout_s = settings.llm_timeout_ms / 1000
        self._retry_max = settings.llm_retry_max

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Send a chat completion request and return the assistant message text."""
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_exc: Exception | None = None
        for attempt in range(self._retry_max + 1):
            try:
                response = self._post("/v1/chat/completions", payload)
                return response["choices"][0]["message"]["content"]
            except LLMError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < self._retry_max:
                    wait = 2 ** attempt
                    logger.warning("DeepSeek request failed (attempt %d/%d), retrying in %ds: %s", attempt + 1, self._retry_max + 1, wait, exc)
                    time.sleep(wait)
            except Exception as exc:
                raise LLMError(f"Unexpected error calling DeepSeek: {exc}") from exc

        raise LLMError(f"DeepSeek request failed after {self._retry_max + 1} attempts: {last_exc}") from last_exc

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Request JSON output and parse it; raises LLMError on invalid JSON."""
        json_messages = list(messages)
        if not any("json" in m.get("content", "").lower() for m in json_messages):
            json_messages.append({
                "role": "system",
                "content": "You must respond with valid JSON only. Do not include markdown fences or extra text.",
            })

        raw = self.chat(json_messages, temperature=temperature, max_tokens=max_tokens)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"DeepSeek returned invalid JSON: {exc}\nRaw: {raw[:400]}") from exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout_s) as client:
            resp = client.post(
                f"{self._base_url}{path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code == 401:
            raise LLMError("DeepSeek API key is invalid or missing (401)")
        if resp.status_code == 429:
            raise LLMError("DeepSeek rate limit exceeded (429)")
        if resp.status_code >= 500:
            raise LLMError(f"DeepSeek server error ({resp.status_code}): {resp.text[:200]}")
        if not resp.is_success:
            raise LLMError(f"DeepSeek API error ({resp.status_code}): {resp.text[:200]}")

        return resp.json()


_client: DeepSeekClient | None = None


def check_llm_available() -> None:
    """Verify LLM is configured and ready.

    Raises LLMUnavailableError when:
    - API key is not configured (empty)
    - Client initialization would fail due to missing configuration
    """
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise LLMUnavailableError("DeepSeek API Key 未配置")


def get_llm_client() -> DeepSeekClient:
    global _client
    if _client is None:
        _client = DeepSeekClient()
    return _client
