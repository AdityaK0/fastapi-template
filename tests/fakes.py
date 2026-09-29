"""A scripted AIProvider: tests queue the model's responses and inspect the requests it received."""
from __future__ import annotations

import copy
import itertools
from collections import deque

from ai.providers.base import AIProvider, Completion, CompletionRequest, ToolCall

_ids = itertools.count(1)


def reply(text: str) -> Completion:
    return Completion(text=text, tool_calls=[], stop_reason="end_turn", model="fake-model", input_tokens=10, output_tokens=5)


def tool(name: str, arguments: dict, text: str = "") -> Completion:
    call = ToolCall(id=f"call_{next(_ids)}", name=name, arguments=arguments)
    return Completion(text=text, tool_calls=[call], stop_reason="tool_use", model="fake-model", input_tokens=10, output_tokens=5)


class ScriptedProvider(AIProvider):
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.responses: deque = deque()
        self.requests: list[CompletionRequest] = []

    def queue(self, *responses) -> None:
        self.responses.extend(responses)

    def complete(self, request: CompletionRequest) -> Completion:
        self.requests.append(copy.deepcopy(request))
        if not self.responses:
            raise AssertionError("ScriptedProvider has no response queued")
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response(request) if callable(response) else response

    def tool_results(self, request_index: int = -1):
        """Tool results sent back to the model in a given request."""
        return [r for m in self.requests[request_index].messages for r in m.tool_results]
