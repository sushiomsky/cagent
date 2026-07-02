"""Minimal OpenAI-compatible HTTP client.

The client intentionally uses only Python's standard library so the first MVP has no
runtime dependency beyond Python itself.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMError(RuntimeError):
    """Raised when the model endpoint fails or returns an unexpected response."""


@dataclass(frozen=True)
class ChatMessage:
    """OpenAI-compatible chat message."""

    role: str
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class OpenAICompatibleClient:
    """Small `/v1/chat/completions` client for Ollama, llama.cpp, vLLM and similar APIs."""

    def __init__(self, *, base_url: str, model: str, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def list_models(self) -> list[str]:
        """Return model IDs from `/v1/models` when the backend supports it."""

        payload = self._request("GET", f"{self.base_url}/models", None)
        models = payload.get("data", [])
        return [str(item.get("id")) for item in models if item.get("id")]

    def complete(
        self,
        *,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call `/v1/chat/completions` and return the assistant text content."""

        body = {
            "model": self.model,
            "messages": [message.as_dict() for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        payload = self._request("POST", f"{self.base_url}/chat/completions", body)

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected chat completion response: {payload!r}") from exc

        if not isinstance(content, str):
            raise LLMError(f"Model response content is not text: {content!r}")
        return content

    def _request(self, method: str, url: str, body: dict[str, Any] | None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"HTTP {exc.code} from {url}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"Could not reach model endpoint {url}: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Endpoint returned invalid JSON: {raw[:1000]}") from exc

        if not isinstance(parsed, dict):
            raise LLMError(f"Endpoint returned non-object JSON: {parsed!r}")
        return parsed
