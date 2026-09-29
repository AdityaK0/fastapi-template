"""
Provider-neutral types for talking to an LLM.

Services, tools and routers only use these types. A provider adapter (see
anthropic_provider.py) translates them to and from its SDK, so switching
providers means writing one new adapter and changing the factory.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]   # JSON Schema; objects must set additionalProperties: false


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


@dataclass
class ChatMessage:
    role: Literal["user", "assistant"]
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    # Provider-native content of an assistant turn inside one tool loop (for
    # example thinking blocks that must be sent back unchanged). Never stored.
    provider_content: Any = None


@dataclass
class CompletionRequest:
    system: str
    messages: list[ChatMessage]
    tools: list[ToolSpec] = field(default_factory=list)


StopReason = Literal["end_turn", "tool_use", "max_tokens", "refusal", "other"]


@dataclass
class Completion:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: StopReason
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    provider_content: Any = None


class AIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def complete(self, request: CompletionRequest) -> Completion:
        """Run one model call. Raises an AIProviderError subclass on failure."""


class AIProviderError(Exception):
    """Base class for provider failures. Messages are for logs, not for users."""


class AIProviderTimeout(AIProviderError):
    pass


class AIProviderBusy(AIProviderError):
    """Rate limited, overloaded, unreachable, or a 5xx from the provider."""


class AIProviderConfigError(AIProviderError):
    """Bad credentials, unknown model, or a request the provider rejects as invalid."""


class AIContextTooLong(AIProviderError):
    pass
