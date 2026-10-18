"""OpenAI-compatible chat completions adapter, with function calling.

One adapter for every provider whose wire format is OpenAI's
``POST {base_url}/chat/completions`` with a Bearer key (OpenAI, OpenRouter,
Groq, Mistral, Qwen, Grok, NVIDIA, DeepSeek, ...). Tool calls are mapped to and
from the provider-neutral types in base.py, so the AI engine is unchanged.

Error handling mirrors OpenCluely's ``ai/errors.js``: HTTP and network failures
become AIProviderError subclasses with a redacted provider detail for the log.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid

import httpx

from .base import (
    AIContextTooLong,
    AIProvider,
    AIProviderBusy,
    AIProviderConfigError,
    AIProviderError,
    AIProviderTimeout,
    ChatMessage,
    Completion,
    CompletionRequest,
    ToolCall,
    ToolSpec,
)

logger = logging.getLogger(__name__)

# OpenAI's reasoning models (o1/o3/o4, gpt-5...) reject `max_tokens` and want
# `max_completion_tokens`; every other compatible endpoint wants `max_tokens`.
_REASONING_MODEL = re.compile(r"^(o[1-9]|gpt-5)", re.IGNORECASE)

# A 400 whose body looks like one of these is a too-long prompt, not bad input.
_CONTEXT_MARKERS = (
    "context length", "context_length", "maximum context", "too long",
    "max tokens", "token limit", "reduce the length", "prompt is too long",
)

# Statuses worth retrying before giving up (and moving to the next provider).
_RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}

_STOP_REASONS = {
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "length": "max_tokens",
    "stop": "end_turn",
    "content_filter": "refusal",
}

# Never leak a key back through an error message/log.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{6,}"),
    re.compile(r"([?&]key=)[^&\s\"']+", re.IGNORECASE),
)
_MAX_DETAIL = 300


def _redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("***", text)
    return " ".join(text.split())[:_MAX_DETAIL]


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        provider_id: str = "openai",
        max_output_tokens: int,
        temperature: float | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ):
        self.name = provider_id
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._extra_headers = extra_headers or {}
        self._max_retries = max(0, max_retries)
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, request: CompletionRequest) -> Completion:
        body: dict = {"model": self.model, "messages": self._to_api_messages(request)}
        body[self._token_param()] = self._max_output_tokens
        if self._temperature is not None:
            body["temperature"] = self._temperature
        if request.tools:
            body["tools"] = [self._to_api_tool(t) for t in request.tools]
            body["tool_choice"] = "auto"

        return self._from_api_response(self._post(body))

    # ── request translation ────────────────────────────────────────────────────

    def _token_param(self) -> str:
        if self.name == "openai" and _REASONING_MODEL.match(self.model or ""):
            return "max_completion_tokens"
        return "max_tokens"

    @staticmethod
    def _to_api_tool(tool: ToolSpec) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }

    def _to_api_messages(self, request: CompletionRequest) -> list[dict]:
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for message in request.messages:
            if message.role == "assistant":
                entry: dict = {"role": "assistant", "content": message.text or None}
                if message.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments or {})},
                        }
                        for call in message.tool_calls
                    ]
                if entry["content"] is None and "tool_calls" not in entry:
                    entry["content"] = ""
                messages.append(entry)
                continue
            for result in message.tool_results:
                messages.append({"role": "tool", "tool_call_id": result.call_id, "content": result.content})
            if message.text:
                messages.append({"role": "user", "content": message.text})
            elif not message.tool_results:
                messages.append({"role": "user", "content": ""})
        return messages

    # ── transport + errors ─────────────────────────────────────────────────────

    def _post(self, body: dict) -> dict:
        url = f"{self._base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        headers.update(self._extra_headers)

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post(url, headers=headers, json=body)
            except httpx.TimeoutException as exc:
                raise AIProviderTimeout(f"{self.name} request timed out") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise AIProviderBusy(f"Could not reach {self.name}") from exc

            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as exc:
                    raise AIProviderError(f"{self.name} returned a non-JSON response") from exc

            if response.status_code in _RETRY_STATUS and attempt < self._max_retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            raise self._error_for(response)

        raise AIProviderBusy(f"{self.name} is unavailable")  # pragma: no cover - loop always returns/raises

    def _error_for(self, response: httpx.Response) -> AIProviderError:
        code = response.status_code
        detail = _provider_detail(response)
        suffix = f": {detail}" if detail else ""
        if code in (401, 403):
            return AIProviderConfigError(f"{self.name} rejected the API key{suffix}")
        if code == 404:
            return AIProviderConfigError(f"{self.name} does not know model '{self.model}'{suffix}")
        if code == 402:
            return AIProviderBusy(f"{self.name} account has insufficient credits{suffix}")
        if code == 400:
            if any(marker in (detail or "").lower() for marker in _CONTEXT_MARKERS):
                return AIContextTooLong(f"{self.name} rejected the prompt as too long{suffix}")
            return AIProviderConfigError(f"{self.name} rejected the request{suffix}")
        if code == 429 or code >= 500:
            return AIProviderBusy(f"{self.name} unavailable ({code}){suffix}")
        return AIProviderConfigError(f"{self.name} error ({code}){suffix}")

    # ── response translation ───────────────────────────────────────────────────

    def _from_api_response(self, data: dict) -> Completion:
        choices = data.get("choices") or []
        if not choices:
            raise AIProviderError(f"{self.name} returned no choices")
        choice = choices[0]
        message = choice.get("message") or {}

        calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            calls.append(ToolCall(
                id=raw.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                name=function.get("name") or "",
                arguments=_parse_arguments(function.get("arguments")),
            ))

        finish = choice.get("finish_reason")
        stop_reason = _STOP_REASONS.get(finish, "other")
        if calls and stop_reason == "end_turn":
            # Some gateways report "stop" even when they emitted tool calls.
            stop_reason = "tool_use"

        usage = data.get("usage") or {}
        return Completion(
            text=_content_text(message.get("content")),
            tool_calls=calls,
            stop_reason=stop_reason,
            model=data.get("model") or self.model,
            input_tokens=usage.get("prompt_tokens") or 0,
            output_tokens=usage.get("completion_tokens") or 0,
        )


def _content_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text") and part.get("text")
        ).strip()
    return ""


def _parse_arguments(arguments) -> dict:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str) and arguments.strip():
        try:
            parsed = json.loads(arguments)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
    return {}


def _provider_detail(response: httpx.Response) -> str | None:
    try:
        text = response.text
    except Exception:  # pragma: no cover - body already consumed/unreadable
        return None
    if not text or not text.strip():
        return None
    detail = text.strip()
    try:
        parsed = json.loads(text)
        error = parsed.get("error") if isinstance(parsed, dict) else None
        if isinstance(error, str):
            detail = error
        elif isinstance(error, dict) and isinstance(error.get("message"), str):
            detail = error["message"]
        elif isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
            detail = parsed["message"]
        elif isinstance(parsed, dict) and isinstance(parsed.get("detail"), str):
            detail = parsed["detail"]
    except ValueError:
        pass
    return _redact(detail) or None
