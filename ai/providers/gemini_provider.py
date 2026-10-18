"""Gemini adapter for the provider-neutral AIProvider interface (google-genai SDK)."""
from __future__ import annotations

import json
import logging
import uuid

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

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

try:  # httpx2 is a drop-in httpx fork some transports use; treat it the same way.
    import httpx2
except ImportError:  # pragma: no cover - optional dependency
    httpx2 = None

logger = logging.getLogger(__name__)

# Finish reasons that mean the model declined to answer rather than finishing.
_REFUSAL_FINISH_REASONS = {
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
    "IMAGE_PROHIBITED_CONTENT",
    "IMAGE_RECITATION",
}

# Finish reasons that signal a broken tool call rather than a usable answer.
_BROKEN_FINISH_REASONS = {"MALFORMED_FUNCTION_CALL", "UNEXPECTED_TOOL_CALL", "TOO_MANY_TOOL_CALLS"}

_TIMEOUT_EXC: tuple[type[BaseException], ...] = (httpx.TimeoutException,)
_TRANSPORT_EXC: tuple[type[BaseException], ...] = (httpx.HTTPError, OSError)
if httpx2 is not None:
    _TIMEOUT_EXC += (httpx2.TimeoutException,)
    _TRANSPORT_EXC += (httpx2.HTTPError,)

_CONTEXT_MARKERS = ("token", "context", "too long", "exceeds", "maximum", "length")


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        max_output_tokens: int,
        temperature: float | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        client: genai.Client | None = None,
    ):
        self.model = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                # HttpOptions.timeout is in milliseconds.
                timeout=int(timeout * 1000),
                retry_options=types.HttpRetryOptions(attempts=max_retries + 1),
            ),
        )

    def complete(self, request: CompletionRequest) -> Completion:
        config_kwargs: dict = {
            "max_output_tokens": self._max_output_tokens,
            "system_instruction": request.system or None,
            # The engine drives the tool loop; never let the SDK invoke tools itself.
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if request.tools:
            config_kwargs["tools"] = [types.Tool(
                function_declarations=[self._to_api_tool(t) for t in request.tools],
            )]
        if self._temperature is not None:
            config_kwargs["temperature"] = self._temperature

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=self._to_contents(request.messages),
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except genai_errors.APIError as exc:
            raise self._map_api_error(exc) from exc
        except _TIMEOUT_EXC as exc:
            raise AIProviderTimeout("Gemini request timed out") from exc
        except _TRANSPORT_EXC as exc:
            raise AIProviderBusy("Could not reach Gemini") from exc
        except ValueError as exc:
            raise AIProviderConfigError(f"Gemini rejected the request: {exc}") from exc
        except genai_errors.FunctionInvocationError as exc:  # pragma: no cover - defensive
            raise AIProviderError("Gemini failed while handling a tool call") from exc

        return self._from_api_response(response)

    # ── error mapping ─────────────────────────────────────────────────────────

    @staticmethod
    def _map_api_error(exc: genai_errors.APIError) -> AIProviderError:
        code = exc.code
        message = (exc.message or "").lower()
        if code in (401, 403, 404):
            return AIProviderConfigError(f"Gemini rejected credentials or model ({code})")
        if code in (408, 504):
            return AIProviderTimeout("Gemini request timed out")
        if code == 400:
            if any(marker in message for marker in _CONTEXT_MARKERS):
                return AIContextTooLong("Prompt too long")
            return AIProviderConfigError(f"Gemini rejected the request: {exc.message}")
        if code == 429 or (code is not None and code >= 500):
            return AIProviderBusy(f"Gemini unavailable ({code})")
        return AIProviderBusy(f"Gemini error ({code})")

    # ── translation ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_api_tool(tool: ToolSpec) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters_json_schema=tool.input_schema,
        )

    def _to_contents(self, messages: list[ChatMessage]) -> list[types.Content]:
        names_by_id = {
            call.id: call.name
            for message in messages if message.role == "assistant"
            for call in message.tool_calls
        }
        contents: list[types.Content] = []
        for message in messages:
            content = self._to_content(message, names_by_id)
            # Gemini wants strict user/model alternation; fold same-role turns together.
            if contents and contents[-1].role == content.role:
                contents[-1] = types.Content(role=content.role, parts=(contents[-1].parts or []) + (content.parts or []))
            else:
                contents.append(content)
        return contents

    @staticmethod
    def _to_content(message: ChatMessage, names_by_id: dict[str, str]) -> types.Content:
        if message.role == "assistant":
            if message.provider_content is not None:
                # Raw model content, replayed unchanged so thought signatures survive.
                return message.provider_content
            parts: list[types.Part] = []
            if message.text:
                parts.append(types.Part.from_text(text=message.text))
            for call in message.tool_calls:
                parts.append(types.Part(function_call=types.FunctionCall(
                    id=call.id, name=call.name, args=call.arguments or {},
                )))
            return types.Content(role="model", parts=parts or [types.Part.from_text(text=" ")])

        parts = []
        for result in message.tool_results:
            parts.append(types.Part(function_response=types.FunctionResponse(
                id=result.call_id,
                name=names_by_id.get(result.call_id, result.call_id),
                response=_tool_response_payload(result),
            )))
        if message.text:
            parts.append(types.Part.from_text(text=message.text))
        return types.Content(role="user", parts=parts or [types.Part.from_text(text=" ")])

    def _from_api_response(self, response: types.GenerateContentResponse) -> Completion:
        candidate = response.candidates[0] if response.candidates else None
        texts: list[str] = []
        calls: list[ToolCall] = []
        parts: list[types.Part] = []

        for part in (candidate.content.parts if candidate and candidate.content else []) or []:
            if part.function_call is not None:
                fc = part.function_call
                call_id = fc.id or f"call_{uuid.uuid4().hex[:12]}"
                arguments = dict(fc.args or {})
                calls.append(ToolCall(id=call_id, name=fc.name, arguments=arguments))
                parts.append(types.Part(
                    function_call=types.FunctionCall(id=call_id, name=fc.name, args=arguments),
                    thought=part.thought,
                    thought_signature=part.thought_signature,
                ))
            else:
                parts.append(part)
                # Skip internal "thinking" summaries; only surface real text.
                if part.text and not part.thought and part.text.strip():
                    texts.append(part.text.strip())

        stop_reason = self._stop_reason(candidate, response, has_tool_calls=bool(calls))
        if stop_reason == "refusal":
            block = response.prompt_feedback.block_reason if response.prompt_feedback else None
            finish = candidate.finish_reason if candidate else None
            logger.warning("Gemini refusal: finish_reason=%s block_reason=%s", finish, block)

        usage = response.usage_metadata
        return Completion(
            text="\n\n".join(texts),
            tool_calls=calls,
            stop_reason=stop_reason,
            model=response.model_version or self.model,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0,
            provider_content=types.Content(role="model", parts=parts) if parts else None,
        )

    @staticmethod
    def _stop_reason(candidate, response, *, has_tool_calls: bool) -> str:
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            return "refusal"
        finish = candidate.finish_reason.name if candidate and candidate.finish_reason else None
        if finish in _REFUSAL_FINISH_REASONS:
            return "refusal"
        if finish in _BROKEN_FINISH_REASONS:
            return "other"
        if finish == "MAX_TOKENS":
            return "max_tokens"
        if finish in (None, "STOP", "FINISH_REASON_UNSPECIFIED"):
            return "tool_use" if has_tool_calls else "end_turn"
        return "other"


def _tool_response_payload(result) -> dict:
    """Gemini function responses must be JSON objects; our tool results are JSON strings."""
    try:
        data = json.loads(result.content)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, dict):
        return data
    if result.is_error:
        return {"error": str(result.content)}
    return {"result": data if data is not None else result.content}
