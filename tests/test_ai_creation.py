"""Create with AI: conversation state, structured proposals, confirmation through TrackerService."""
from datetime import date, timedelta

import pytest

from ai.providers.base import AIProviderBusy, AIProviderTimeout, AIContextTooLong
from tests.fakes import reply, tool

TODAY = date.today()


def plan(**overrides):
    base = {
        "name": "30-Day Walking Habit",
        "description": "Build a daily walking routine.",
        "duration_days": 30,
        "start_date": TODAY.isoformat(),
        "habits": [{"name": "Walk 8,000 steps"}, {"name": "Drink 2L water"}, {"name": "Log weight"}],
    }
    return {**base, **overrides}


def start(client, headers):
    response = client.post("/ai/tracker-conversations", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def send(client, headers, conversation_id, content):
    return client.post(f"/ai/tracker-conversations/{conversation_id}/messages", headers=headers, json={"content": content})


def test_start_creates_conversation_with_greeting(client, alice):
    convo = start(client, alice)
    assert convo["purpose"] == "tracker_creation"
    assert convo["status"] == "discovery"
    assert convo["tracker_id"] is None
    assert [m["role"] for m in convo["messages"]] == ["assistant"]
    assert "What would you like to achieve" in convo["messages"][0]["content"]


def test_follow_up_question_is_persisted_and_moves_to_gathering(client, alice, provider):
    convo = start(client, alice)
    provider.queue(reply("Got it. What does a typical day look like for you?"))

    response = send(client, alice, convo["id"], "I want to lose weight")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "gathering_context"
    assert [(m["role"], m["content"]) for m in body["messages"][1:]] == [
        ("user", "I want to lose weight"),
        ("assistant", "Got it. What does a typical day look like for you?"),
    ]
    request = provider.requests[0]
    # The greeting is dropped so the model's context starts with the user's message.
    assert [m.role for m in request.messages] == ["user"]
    assert TODAY.isoformat() in request.system
    assert [t.name for t in request.tools] == ["propose_tracker"]
    # The conversation survives a reload.
    reloaded = client.get(f"/ai/tracker-conversations/{convo['id']}", headers=alice).json()
    assert len(reloaded["messages"]) == 3


def test_proposal_is_stored_as_structured_tracker_create(client, alice, provider):
    convo = start(client, alice)
    provider.queue(tool("propose_tracker", plan(), text="Here's a plan that fits your mornings."))

    body = send(client, alice, convo["id"], "I want to walk more, 30 days, simple").json()
    assert body["status"] == "awaiting_confirmation"
    proposal = body["current_proposal"]
    assert proposal["version"] == 1 and proposal["source"] == "assistant" and proposal["kind"] == "tracker_create"
    assert proposal["payload"]["habits"] == [
        {"name": "Walk 8,000 steps", "position": 0},
        {"name": "Drink 2L water", "position": 1},
        {"name": "Log weight", "position": 2},
    ]
    assistant = body["messages"][-1]
    assert assistant["content"] == "Here's a plan that fits your mornings."
    assert assistant["proposal_id"] == proposal["id"]
    assert body["title"] == "30-Day Walking Habit"


def test_invalid_proposal_is_returned_to_the_model_as_a_tool_error(client, alice, provider):
    convo = start(client, alice)
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    provider.queue(
        tool("propose_tracker", plan(habits=[{"name": "Walk"}, {"name": "walk"}])),
        tool("propose_tracker", plan(start_date=yesterday)),
        tool("propose_tracker", plan(habits=[])),
        tool("propose_tracker", plan()),
    )
    body = send(client, alice, convo["id"], "make it").json()
    assert body["current_proposal"]["version"] == 1
    errors = [provider.tool_results(i)[-1] for i in (1, 2, 3)]
    assert all(r.is_error for r in errors)
    assert "unique" in errors[0].content
    assert "before today" in errors[1].content
    assert "habits" in errors[2].content


def test_generate_now_forces_a_proposal_after_one_reminder(client, alice, provider):
    convo = start(client, alice)
    provider.queue(reply("How much time do you have each day?"))
    send(client, alice, convo["id"], "Read more books")

    provider.queue(reply("Sure, one moment."), tool("propose_tracker", plan(name="Reading Habit")))
    response = client.post(f"/ai/tracker-conversations/{convo['id']}/generate", headers=alice)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_proposal"]["payload"]["name"] == "Reading Habit"
    reminder = provider.requests[-1].messages[-1]
    assert reminder.role == "user" and "propose_tracker" in reminder.text


def test_generate_requires_a_goal_first(client, alice):
    convo = start(client, alice)
    response = client.post(f"/ai/tracker-conversations/{convo['id']}/generate", headers=alice)
    assert response.status_code == 409
    assert response.json()["error_code"] == "INVALID_CONVERSATION_STATE"


def test_revision_by_chat_creates_new_version_and_supersedes_old(client, alice, provider):
    convo = start(client, alice)
    provider.queue(tool("propose_tracker", plan()))
    send(client, alice, convo["id"], "walking plan")

    provider.queue(tool("propose_tracker", plan(habits=[{"name": "Walk 8,000 steps"}, {"name": "Log weight"}])))
    body = send(client, alice, convo["id"], "Remove the water habit").json()
    assert body["current_proposal"]["version"] == 2
    assert [p["status"] for p in body["proposals"]] == ["superseded", "pending"]
    # The model saw the proposal that was on screen when asked for the change.
    assert "<current_proposal>" in provider.requests[-1].system
    assert "Drink 2L water" in provider.requests[-1].system


def test_user_customisation_creates_user_version(client, alice, provider):
    convo = start(client, alice)
    provider.queue(tool("propose_tracker", plan()))
    send(client, alice, convo["id"], "walking plan")

    edited = plan(name="My Walks", duration_days=21, habits=[{"name": "Walk after lunch"}])
    response = client.put(f"/ai/tracker-conversations/{convo['id']}/proposal", headers=alice, json=edited)
    assert response.status_code == 200, response.text
    current = response.json()["current_proposal"]
    assert current["version"] == 2 and current["source"] == "user"
    assert current["payload"]["duration_days"] == 21

    bad = client.put(f"/ai/tracker-conversations/{convo['id']}/proposal", headers=alice, json=plan(habits=[]))
    assert bad.status_code == 422
    assert bad.json()["error_code"] == "VALIDATION_ERROR"

    provider.queue(reply("Looks good!"))
    send(client, alice, convo["id"], "thanks")
    assert "the user edited it themselves" in provider.requests[-1].system


def test_confirm_creates_tracker_through_tracker_service(client, alice, provider, monkeypatch):
    from trackers.schema import TrackerCreate
    from trackers.service import TrackerService

    calls = []
    original = TrackerService.create

    def spy(self, user_id, data):
        calls.append(data)
        return original(self, user_id, data)

    monkeypatch.setattr(TrackerService, "create", spy)

    convo = start(client, alice)
    provider.queue(tool("propose_tracker", plan()))
    send(client, alice, convo["id"], "walking plan")

    response = client.post(f"/ai/tracker-conversations/{convo['id']}/confirm", headers=alice, json={"proposal_version": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(calls) == 1 and type(calls[0]) is TrackerCreate
    assert body["conversation"]["status"] == "tracker_created"
    assert body["conversation"]["tracker_id"] == body["tracker_id"]
    assert body["conversation"]["current_proposal"] is None

    tracker = client.get(f"/trackers/{body['tracker_id']}", headers=alice).json()
    assert tracker["name"] == "30-Day Walking Habit"
    assert tracker["duration_days"] == 30 and tracker["status"] == "active"
    assert [(h["name"], h["position"]) for h in tracker["habits"]] == [
        ("Walk 8,000 steps", 0), ("Drink 2L water", 1), ("Log weight", 2),
    ]

    # Confirming again (double click) returns the same tracker instead of a duplicate.
    again = client.post(f"/ai/tracker-conversations/{convo['id']}/confirm", headers=alice, json={"proposal_version": 1})
    assert again.status_code == 200 and again.json()["tracker_id"] == body["tracker_id"]
    assert len(calls) == 1
    assert len(client.get("/trackers", headers=alice).json()) == 1

    closed = send(client, alice, convo["id"], "one more thing")
    assert closed.status_code == 409 and closed.json()["error_code"] == "CONVERSATION_CLOSED"


def test_confirm_rejects_stale_version(client, alice, provider):
    convo = start(client, alice)
    provider.queue(tool("propose_tracker", plan()), tool("propose_tracker", plan(name="v2")))
    send(client, alice, convo["id"], "plan")
    send(client, alice, convo["id"], "change it")

    response = client.post(f"/ai/tracker-conversations/{convo['id']}/confirm", headers=alice, json={"proposal_version": 1})
    assert response.status_code == 409
    assert response.json()["error_code"] == "PROPOSAL_VERSION_MISMATCH"
    assert client.get("/trackers", headers=alice).json() == []


def test_confirm_without_proposal_is_rejected(client, alice):
    convo = start(client, alice)
    response = client.post(f"/ai/tracker-conversations/{convo['id']}/confirm", headers=alice, json={"proposal_version": 1})
    assert response.status_code == 409


def test_abandon_closes_the_conversation(client, alice, provider):
    convo = start(client, alice)
    assert client.delete(f"/ai/tracker-conversations/{convo['id']}", headers=alice).status_code == 204
    assert client.get("/ai/tracker-conversations", headers=alice).json() == []
    assert send(client, alice, convo["id"], "hi").status_code == 409
    listed = client.get("/ai/tracker-conversations?status=all", headers=alice).json()
    assert [c["status"] for c in listed] == ["abandoned"]


def test_other_users_cannot_see_or_use_a_conversation(client, alice, bob, provider):
    convo = start(client, alice)
    provider.queue(tool("propose_tracker", plan()))
    send(client, alice, convo["id"], "plan")

    base = f"/ai/tracker-conversations/{convo['id']}"
    for response in (
        client.get(base, headers=bob),
        send(client, bob, convo["id"], "hi"),
        client.post(f"{base}/confirm", headers=bob, json={"proposal_version": 1}),
        client.put(f"{base}/proposal", headers=bob, json=plan()),
        client.delete(base, headers=bob),
    ):
        assert response.status_code == 404
        assert response.json()["error_code"] == "CONVERSATION_NOT_FOUND"
    assert client.get("/ai/tracker-conversations", headers=bob).json() == []
    assert client.get(base, headers=alice).json()["status"] == "awaiting_confirmation"


def test_requires_authentication(client):
    assert client.post("/ai/tracker-conversations").status_code == 401


@pytest.mark.parametrize("content", ["", "   ", "x" * 2001])
def test_message_validation(client, alice, content):
    convo = start(client, alice)
    response = send(client, alice, convo["id"], content)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("error, status, code", [
    (AIProviderTimeout("slow"), 504, "AI_TIMEOUT"),
    (AIProviderBusy("429"), 503, "AI_BUSY"),
    (AIContextTooLong("big"), 422, "AI_CONTEXT_TOO_LONG"),
])
def test_provider_failures_map_to_safe_errors_and_persist_nothing(client, alice, provider, error, status, code):
    convo = start(client, alice)
    provider.queue(error)
    response = send(client, alice, convo["id"], "I want to run a 5k")
    assert response.status_code == status
    body = response.json()
    assert body["error_code"] == code and body["success"] is False
    assert "slow" not in body["message"] and "429" not in body["message"]
    assert len(client.get(f"/ai/tracker-conversations/{convo['id']}", headers=alice).json()["messages"]) == 1


def test_malformed_tool_call_loop_is_bounded(client, alice, provider, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "AI_MAX_TOOL_ROUNDS", 3)
    convo = start(client, alice)
    provider.queue(*[tool("propose_tracker", {"name": "x"}) for _ in range(3)])
    response = send(client, alice, convo["id"], "plan")
    assert response.status_code == 502
    assert response.json()["error_code"] == "AI_INVALID_OUTPUT"


def test_refusal_is_reported(client, alice, provider):
    from ai.providers.base import Completion
    convo = start(client, alice)
    provider.queue(Completion(text="", tool_calls=[], stop_reason="refusal", model="fake-model"))
    response = send(client, alice, convo["id"], "something")
    assert response.status_code == 422 and response.json()["error_code"] == "AI_REFUSED"


def test_rate_limit(client, alice, provider, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_PER_MINUTE", 2)
    convo = start(client, alice)
    provider.queue(reply("one"), reply("two"))
    assert send(client, alice, convo["id"], "a").status_code == 200
    assert send(client, alice, convo["id"], "b").status_code == 200
    limited = send(client, alice, convo["id"], "c")
    assert limited.status_code == 429 and limited.json()["error_code"] == "AI_RATE_LIMITED"


def test_ai_disabled_returns_not_configured(client, alice, monkeypatch):
    import main
    from ai.providers.factory import get_ai_provider
    from config import settings
    main.app.dependency_overrides.pop(get_ai_provider)
    monkeypatch.setattr(settings, "AI_API_KEY", None)
    response = client.post("/ai/tracker-conversations", headers=alice)
    assert response.status_code == 503 and response.json()["error_code"] == "AI_NOT_CONFIGURED"
    assert client.get("/ai/config", headers=alice).json() == {"enabled": False, "provider": None, "model": None}


def test_context_window_keeps_first_message_and_recent_turns(client, alice, provider, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "AI_CONTEXT_MAX_MESSAGES", 4)
    convo = start(client, alice)
    for i in range(4):
        provider.queue(reply(f"answer {i}"))
        send(client, alice, convo["id"], f"message {i}")
    texts = [m.text for m in provider.requests[-1].messages]
    assert texts[0] == "message 0"
    assert texts[-1] == "message 3"
    assert len(texts) == 5    # 4 stored (first + 3 most recent) + the new message
