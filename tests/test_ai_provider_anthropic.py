"""AnthropicProvider against the real SDK with a mocked HTTP transport (no network)."""
import json

import anthropic
import httpx2
import pytest

from ai.providers.anthropic_provider import REFUSAL_FALLBACK_BETA, AnthropicProvider
from ai.providers.base import (
    AIContextTooLong,
    AIProviderBusy,
    AIProviderConfigError,
    AIProviderTimeout,
    ChatMessage,
    CompletionRequest,
    ToolCall,
    ToolResult,
    ToolSpec,
)

TOOL = ToolSpec("get_tracker_overview", "Overview", {"type": "object", "properties": {}, "required": [], "additionalProperties": False})


def make_provider(handler, **kwargs):
    client = anthropic.Anthropic(
        api_key="test-key", max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicProvider(api_key=None, model="claude-opus-5", max_output_tokens=16000, client=client, **kwargs)


def message(content, stop_reason="end_turn"):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 7, "cache_read_input_tokens": 3},
    }


def test_request_shape_and_text_response():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx2.Response(200, json=message([{"type": "text", "text": "Hello there"}]))

    provider = make_provider(handler)
    result = provider.complete(CompletionRequest(
        system="system prompt", messages=[ChatMessage("user", text="hi")], tools=[TOOL],
    ))
    body = seen["body"]
    assert body["model"] == "claude-opus-5" and body["max_tokens"] == 16000
    assert body["system"] == "system prompt"
    assert body["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    assert body["tools"][0]["strict"] is True and body["tools"][0]["name"] == "get_tracker_overview"
    assert body["fallbacks"] == "default" and REFUSAL_FALLBACK_BETA in seen["beta"]
    assert body["cache_control"] == {"type": "ephemeral"}
    assert "temperature" not in body and "output_config" not in body
    assert result.text == "Hello there" and result.stop_reason == "end_turn"
    assert result.input_tokens == 15 and result.output_tokens == 7


def test_optional_settings_are_sent_only_when_configured():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx2.Response(200, json=message([{"type": "text", "text": "ok"}]))

    make_provider(handler, effort="low", temperature=0.3, refusal_fallback=False).complete(
        CompletionRequest(system="s", messages=[ChatMessage("user", text="hi")])
    )
    assert seen["body"]["output_config"] == {"effort": "low"}
    assert seen["body"]["temperature"] == 0.3
    assert "fallbacks" not in seen["body"] and not seen["beta"]


def test_tool_use_round_trip_echoes_assistant_content_unchanged():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx2.Response(200, json=message([
                {"type": "thinking", "thinking": "", "signature": "sig-abc"},
                {"type": "text", "text": "Let me check."},
                {"type": "tool_use", "id": "toolu_1", "name": "get_tracker_overview", "input": {}},
            ], stop_reason="tool_use"))
        return httpx2.Response(200, json=message([{"type": "text", "text": "Done"}]))

    provider = make_provider(handler)
    first = provider.complete(CompletionRequest(system="s", messages=[ChatMessage("user", text="hi")], tools=[TOOL]))
    assert first.stop_reason == "tool_use"
    assert first.tool_calls == [ToolCall(id="toolu_1", name="get_tracker_overview", arguments={})]

    provider.complete(CompletionRequest(system="s", tools=[TOOL], messages=[
        ChatMessage("user", text="hi"),
        ChatMessage("assistant", text=first.text, tool_calls=first.tool_calls, provider_content=first.provider_content),
        ChatMessage("user", tool_results=[ToolResult("toolu_1", '{"ok": true}')]),
    ]))
    assistant, results = calls[1]["messages"][1], calls[1]["messages"][2]
    assert [b["type"] for b in assistant["content"]] == ["thinking", "text", "tool_use"]
    assert assistant["content"][0]["signature"] == "sig-abc"
    assert results["content"] == [{"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"ok": true}', "is_error": False}]


def test_refusal_stop_reason():
    provider = make_provider(lambda r: httpx2.Response(200, json=message([], stop_reason="refusal")))
    result = provider.complete(CompletionRequest(system="s", messages=[ChatMessage("user", text="hi")]))
    assert result.stop_reason == "refusal" and result.text == ""


def _error(status, error_type, text):
    return lambda r: httpx2.Response(status, json={"type": "error", "error": {"type": error_type, "message": text}})


@pytest.mark.parametrize("handler, expected", [
    (_error(429, "rate_limit_error", "slow down"), AIProviderBusy),
    (_error(529, "overloaded_error", "overloaded"), AIProviderBusy),
    (_error(500, "api_error", "boom"), AIProviderBusy),
    (_error(401, "authentication_error", "bad key"), AIProviderConfigError),
    (_error(404, "not_found_error", "no such model"), AIProviderConfigError),
    (_error(400, "invalid_request_error", "prompt is too long: 1000001 tokens > 1000000 maximum"), AIContextTooLong),
    (_error(400, "invalid_request_error", "messages: bad"), AIProviderConfigError),
])
def test_http_errors_map_to_provider_errors(handler, expected):
    with pytest.raises(expected):
        make_provider(handler).complete(CompletionRequest(system="s", messages=[ChatMessage("user", text="hi")]))


def test_timeout_maps_to_provider_timeout():
    def handler(request):
        raise httpx2.ReadTimeout("timed out", request=request)

    with pytest.raises(AIProviderTimeout):
        make_provider(handler).complete(CompletionRequest(system="s", messages=[ChatMessage("user", text="hi")]))


def test_connection_error_maps_to_busy():
    def handler(request):
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(AIProviderBusy):
        make_provider(handler).complete(CompletionRequest(system="s", messages=[ChatMessage("user", text="hi")]))
