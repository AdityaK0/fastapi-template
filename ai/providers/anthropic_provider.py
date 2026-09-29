"""Claude adapter for the provider-neutral AIProvider interface."""
from __future__ import annotations

import logging

import anthropic

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

# Server-side refusal fallback: if a safety classifier declines the request,
# the API re-runs it on Anthropic's recommended fallback model in the same call.
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_STOP_REASONS = {
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "model_context_window_exceeded": "max_tokens",
    "refusal": "refusal",
}


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        max_output_tokens: int,
        effort: str | None = None,
        temperature: float | None = None,
        refusal_fallback: bool = True,
        timeout: float = 60.0,
        max_retries: int = 2,
        client: anthropic.Anthropic | None = None,
    ):
        self.model = model
        self._max_output_tokens = max_output_tokens
        self._effort = effort or None
        self._temperature = temperature
        self._refusal_fallback = refusal_fallback
        self._client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def complete(self, request: CompletionRequest) -> Completion:
        params: dict = {
            "model": self.model,
            "max_tokens": self._max_output_tokens,
            "system": request.system,
            "messages": [self._to_api_message(m) for m in request.messages],
            # Caches the prompt prefix; tool loops resend it several times per turn.
            "cache_control": {"type": "ephemeral"},
        }
        if request.tools:
            params["tools"] = [self._to_api_tool(t) for t in request.tools]
        if self._effort:
            params["output_config"] = {"effort": self._effort}
        if self._temperature is not None:
            # Sampling params are no longer SDK arguments; models that still honour
            # them read them from the body. Opus 4.7+ rejects them with a 400.
            params["extra_body"] = {"temperature": self._temperature}
        if self._refusal_fallback:
            params["betas"] = [REFUSAL_FALLBACK_BETA]
            params["fallbacks"] = "default"

        try:
            response = self._client.beta.messages.create(**params)
        except anthropic.APITimeoutError as exc:
            raise AIProviderTimeout("Anthropic request timed out") from exc
        except (anthropic.RateLimitError, anthropic.OverloadedError, anthropic.ServiceUnavailableError) as exc:
            raise AIProviderBusy(f"Anthropic unavailable ({exc.status_code})") from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError) as exc:
            raise AIProviderConfigError(f"Anthropic rejected credentials or model ({exc.status_code})") from exc
        except anthropic.RequestTooLargeError as exc:
            raise AIContextTooLong("Request too large") from exc
        except anthropic.BadRequestError as exc:
            # The API has no dedicated error type for an over-long prompt.
            if "prompt is too long" in str(exc.message).lower():
                raise AIContextTooLong("Prompt too long") from exc
            raise AIProviderConfigError(f"Anthropic rejected the request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderBusy(f"Anthropic error ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderBusy("Could not reach Anthropic") from exc
        except anthropic.AnthropicError as exc:
            raise AIProviderError(f"Anthropic client error: {type(exc).__name__}") from exc

        return self._from_api_response(response)

    # ── translation ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_api_tool(tool: ToolSpec) -> dict:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "strict": True,
        }

    @staticmethod
    def _to_api_message(message: ChatMessage) -> dict:
        if message.role == "assistant":
            if message.provider_content is not None:
                return {"role": "assistant", "content": message.provider_content}
            blocks: list[dict] = []
            if message.text:
                blocks.append({"type": "text", "text": message.text})
            for call in message.tool_calls:
                blocks.append({"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments})
            return {"role": "assistant", "content": blocks}

        blocks = [
            {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
            for r in message.tool_results
        ]
        if message.text:
            blocks.append({"type": "text", "text": message.text})
        return {"role": "user", "content": blocks}

    def _from_api_response(self, response) -> Completion:
        texts, calls = [], []
        for block in response.content:
            if block.type == "text" and block.text.strip():
                texts.append(block.text.strip())
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
        stop_reason = _STOP_REASONS.get(response.stop_reason or "", "other")
        if stop_reason == "refusal":
            logger.warning("Anthropic refusal: %s", getattr(response, "stop_details", None))
        usage = response.usage
        return Completion(
            text="\n\n".join(texts),
            tool_calls=calls,
            stop_reason=stop_reason,
            model=response.model,
            input_tokens=(usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0),
            output_tokens=usage.output_tokens or 0,
            provider_content=response.content,
        )
