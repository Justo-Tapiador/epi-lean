"""LLM providers for EPI-LEAN's AI layer (standard library only).

A provider is anything with ``name``, ``model`` and
``complete(system, prompt, max_tokens) -> str``. Three implementations:

* ``AnthropicProvider``: Anthropic Messages API.
* ``OpenAICompatibleProvider``: any ``/chat/completions`` server
  (OpenAI, vLLM, Ollama, LM Studio...), which also covers fully local
  models for confidential code.
* ``CassetteProvider``: record/replay wrapper. LLM output is not
  deterministic, so an audit that used a model is made reproducible by
  *recording* the exchange and replaying it later, offline.

API keys are read from the environment only (never from CLI arguments,
which leak into shell history and process listings).

NOTE: the two network providers were written against the public API
documentation and are covered by tests with a faked transport; they have
not been exercised against the live services in this repository's CI.
"""

import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ProviderError(RuntimeError):
    """Raised for any provider failure (network, auth, bad response)."""


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> str: ...


def _post_json(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise ProviderError(f"HTTP {error.code} from {url}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ProviderError(f"request to {url} failed: {error}") from error


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None, timeout: int = 120):
        self.model = model
        self._key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._timeout = timeout
        if not self._key:
            raise ProviderError("ANTHROPIC_API_KEY is not set in the environment")

    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        data = _post_json(
            ANTHROPIC_URL,
            {"x-api-key": self._key, "anthropic-version": ANTHROPIC_VERSION},
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            self._timeout,
        )
        try:
            return "".join(
                block["text"] for block in data["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as error:
            raise ProviderError(f"unexpected Anthropic response shape: {error}") from error


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        timeout: int = 120,
    ):
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key or os.environ.get("EPILEAN_API_KEY", "")
        self._timeout = timeout

    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        headers = {"authorization": f"Bearer {self._key}"} if self._key else {}
        data = _post_json(
            self._url,
            headers,
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            self._timeout,
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderError(f"unexpected chat response shape: {error}") from error


def exchange_key(system: str, prompt: str) -> str:
    """Stable key of one request (used for cassettes and trail hashes)."""
    return hashlib.sha256(f"{system}\0{prompt}".encode()).hexdigest()


class CassetteProvider:
    """Record/replay wrapper making model-assisted audits reproducible.

    With ``inner`` set, unseen requests are sent to it and recorded;
    without it (pure replay), an unseen request is an error — a replay
    never silently falls back to a live model.
    """

    def __init__(self, path: Path, inner: LLMProvider | None = None):
        self.path = Path(path)
        self.inner = inner
        self.name = f"cassette({inner.name})" if inner else "cassette"
        self.model = inner.model if inner else "recorded"
        self._store: dict[str, dict] = {}
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._store[row["key"]] = row
        if inner is None and self._store:
            first = next(iter(self._store.values()))
            self.model = first.get("model", "recorded")

    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        key = exchange_key(system, prompt)
        if key in self._store:
            return self._store[key]["response"]
        if self.inner is None:
            raise ProviderError(
                "request not found in cassette (replay mode never calls a live model)"
            )
        response = self.inner.complete(system, prompt, max_tokens)
        row = {
            "key": key,
            "provider": self.inner.name,
            "model": self.inner.model,
            "response": response,
        }
        self._store[key] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return response


def make_provider(
    kind: str,
    model: str | None,
    base_url: str | None = None,
    cassette: Path | None = None,
) -> LLMProvider:
    """Build a provider from CLI-level settings."""
    if kind == "replay":
        if cassette is None:
            raise ProviderError("--provider replay requires --cassette")
        return CassetteProvider(cassette)
    if not model:
        raise ProviderError(
            "--model is required for live providers (no default is assumed, "
            "so a stale model name can never be used silently)"
        )
    if kind == "anthropic":
        inner: LLMProvider = AnthropicProvider(model)
    elif kind == "openai-compatible":
        inner = OpenAICompatibleProvider(model, base_url or "http://localhost:11434/v1")
    else:
        raise ProviderError(f"unknown provider {kind!r}")
    return CassetteProvider(cassette, inner) if cassette else inner
