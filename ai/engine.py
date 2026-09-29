"""
AIService — the provider-agnostic core that runs one assistant turn.

generate_response()           a conversational turn; the model may call tools
                              (bounded by AI_MAX_TOOL_ROUNDS) before answering.
generate_structured_output()  a turn that must end in a specific tool call whose
                              arguments are validated by that toolset, e.g. a
                              tracker proposal. The model gets one reminder if it
                              answers in plain text instead.

Provider failures become AppExceptions with stable error codes and user-safe
messages; provider details go to the log only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from config import settings
from utils.exceptions import AppException

from .providers.base import (
    AIContextTooLong,
    AIProvider,
    AIProviderBusy,
    AIProviderConfigError,
    AIProviderError,
    AIProviderTimeout,
    ChatMessage,
    Completion,
    CompletionRequest,
)
from .tools import ToolOutcome, Toolset

logger = logging.getLogger(__name__)


@dataclass
class AssistantTurn:
    text: str
    outcome: ToolOutcome | None = None          # set when a proposal tool ended the turn
    tool_calls: list[dict] = field(default_factory=list)
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def _provider_failure(exc: AIProviderError) -> AppException:
    if isinstance(exc, AIProviderTimeout):
        return AppException("The assistant took too long to respond. Please try again.", 504, "AI_TIMEOUT")
    if isinstance(exc, AIProviderBusy):
        return AppException("The assistant is busy right now. Please try again in a moment.", 503, "AI_BUSY")
    if isinstance(exc, AIContextTooLong):
        return AppException(
            "This conversation has grown too long for the assistant. Start a new one to continue.",
            422, "AI_CONTEXT_TOO_LONG",
        )
    if isinstance(exc, AIProviderConfigError):
        return AppException("The assistant isn't available right now.", 502, "AI_PROVIDER_ERROR")
    return AppException("The assistant isn't available right now.", 502, "AI_PROVIDER_ERROR")


def _invalid_output(reason: str) -> AppException:
    logger.warning("AI invalid output: %s", reason)
    return AppException("The assistant returned an unexpected response. Please try again.", 502, "AI_INVALID_OUTPUT")


class AIService:
    def __init__(self, provider: AIProvider, max_tool_rounds: int | None = None):
        self._provider = provider
        self._max_rounds = max_tool_rounds or settings.AI_MAX_TOOL_ROUNDS

    def generate_response(
        self,
        system: str,
        messages: list[ChatMessage],
        toolset: Toolset | None = None,
        *,
        require_tool: str | None = None,
    ) -> AssistantTurn:
        conversation = list(messages)
        turn = AssistantTurn(text="")
        specs = toolset.specs() if toolset else []
        reminded = False

        for _ in range(self._max_rounds):
            completion = self._complete(CompletionRequest(system=system, messages=conversation, tools=specs))
            turn.model = completion.model
            turn.input_tokens += completion.input_tokens
            turn.output_tokens += completion.output_tokens

            if completion.stop_reason == "refusal":
                raise AppException(
                    "The assistant can't help with that request. Try rephrasing it.", 422, "AI_REFUSED"
                )

            if not completion.tool_calls:
                if completion.stop_reason == "max_tokens" and not completion.text:
                    raise _invalid_output("hit max_tokens before producing text")
                if require_tool and not reminded:
                    reminded = True
                    conversation.append(ChatMessage(
                        "assistant", text=completion.text or "(no reply)",
                        provider_content=completion.provider_content if completion.text else None,
                    ))
                    conversation.append(ChatMessage("user", text=f"Please call the {require_tool} tool now."))
                    continue
                if require_tool:
                    raise _invalid_output(f"model did not call {require_tool}")
                if not completion.text:
                    raise _invalid_output("empty reply")
                turn.text = completion.text
                self._log(turn)
                return turn

            if completion.stop_reason == "max_tokens":
                raise _invalid_output("tool call cut off by max_tokens")

            results, terminal = [], None
            for call in completion.tool_calls:
                outcome = toolset.execute(call) if toolset else None
                if outcome is None:
                    raise _invalid_output(f"tool call {call.name} with no tools offered")
                turn.tool_calls.append({"name": call.name, "arguments": call.arguments, "ok": not outcome.result.is_error})
                results.append(outcome.result)
                if outcome.terminal and not outcome.result.is_error and terminal is None:
                    terminal = outcome

            if terminal is not None:
                turn.text = completion.text
                turn.outcome = terminal
                self._log(turn)
                return turn

            conversation.append(ChatMessage(
                "assistant", text=completion.text, tool_calls=completion.tool_calls,
                provider_content=completion.provider_content,
            ))
            conversation.append(ChatMessage("user", tool_results=results))

        raise _invalid_output(f"no answer after {self._max_rounds} model calls")

    def generate_structured_output(self, system: str, messages: list[ChatMessage], toolset: Toolset, tool_name: str) -> AssistantTurn:
        turn = self.generate_response(system, messages, toolset, require_tool=tool_name)
        if turn.outcome is None:
            raise _invalid_output(f"{tool_name} was not produced")
        return turn

    def _complete(self, request: CompletionRequest) -> Completion:
        try:
            return self._provider.complete(request)
        except AIProviderError as exc:
            logger.warning("AI provider %s failed: %s", self._provider.name, exc)
            raise _provider_failure(exc) from exc

    def _log(self, turn: AssistantTurn) -> None:
        logger.info(
            "AI turn model=%s tools=%s input_tokens=%d output_tokens=%d",
            turn.model, [c["name"] for c in turn.tool_calls], turn.input_tokens, turn.output_tokens,
        )
