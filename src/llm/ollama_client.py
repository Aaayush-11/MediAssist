from __future__ import annotations

from typing import Any

import httpx

from src.config import settings


class OllamaError(Exception):
    """Base exception for Ollama client errors."""


class OllamaConnectionError(OllamaError):
    """Raised when the Ollama server cannot be reached or times out."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an HTTP error or an unexpected response."""


def _normalize_model_name(name: str) -> str:
    """Normalize a model name so an omitted tag is equivalent to ':latest'."""
    name = name.strip()
    # Only the final path segment can carry a tag (a registry host may contain ':port').
    last_segment = name.rsplit("/", 1)[-1]
    if ":" not in last_segment:
        return f"{name}:latest"
    return name


class OllamaClient:
    """Async client for a local Ollama server."""

    def __init__(self, timeout: float = 120.0, connect_timeout: float = 5.0) -> None:
        self.base_url: str = settings.ollama_base_url.rstrip("/")
        self.model: str = settings.ollama_model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=connect_timeout),
        )

    async def _request(
        self,
        method: str,
        path: str,
        expect_json: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a request and return the parsed JSON object, raising meaningful errors.

        If ``expect_json`` is False, the body is not parsed and an empty dict is
        returned after a successful (2xx) response.
        """
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure the Ollama server is running."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError(
                f"Request to Ollama at {self.base_url}{path} timed out."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaResponseError(
                f"Ollama returned HTTP {exc.response.status_code} for {path}: "
                f"{exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaConnectionError(
                f"Request to Ollama at {self.base_url}{path} failed: {exc}"
            ) from exc

        if not expect_json:
            return {}

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaResponseError(
                f"Ollama returned invalid JSON for {path}."
            ) from exc

        if not isinstance(data, dict):
            raise OllamaResponseError(
                f"Unexpected response type from {path}: expected a JSON object, "
                f"got {type(data).__name__}."
            )
        return data

    async def check_connection(self) -> bool:
        """Return True if the Ollama server is reachable; raise OllamaError otherwise."""
        # The root endpoint returns plain text ("Ollama is running"), not JSON.
        await self._request("GET", "/", expect_json=False)
        return True

    async def list_models(self) -> list[str]:
        """Return the names of models available locally via /api/tags."""
        data = await self._request("GET", "/api/tags")
        models = data.get("models")
        if not isinstance(models, list):
            raise OllamaResponseError(
                "Unexpected response from /api/tags: missing 'models' list."
            )

        names: list[str] = []
        for entry in models:
            name = entry.get("name") if isinstance(entry, dict) else None
            if not isinstance(name, str):
                raise OllamaResponseError(
                    "Unexpected response from /api/tags: model entry missing 'name'."
                )
            names.append(name)
        return names

    async def check_model(self) -> bool:
        """Return True if the configured model is available locally."""
        available = await self.list_models()
        target = _normalize_model_name(self.model)
        return any(_normalize_model_name(name) == target for name in available)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        """Send chat messages to the configured model and return the reply text."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        data = await self._request("POST", "/api/chat", json=payload)

        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaResponseError(
                "Unexpected response from /api/chat: missing 'message' object."
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise OllamaResponseError(
                "Unexpected response from /api/chat: missing message 'content'."
            )
        return content

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> OllamaClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()