"""Regression tests for the pre-existing app: the AI layer must not change any of this."""
from datetime import date, timedelta

from tests.conftest import create_tracker, register


def test_auth_register_login_me_refresh_logout(client):
    headers = register(client, "carol")
    assert client.get("/auth/me", headers=headers).json()["username"] == "carol"

    login = client.post("/auth/login", json={"username": "carol", "password": "password123"})
    assert login.status_code == 200
    tokens = login.json()
    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.json()["access_token"]
    assert client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401

    bad = client.post("/auth/login", json={"username": "carol", "password": "wrong-password"})
    assert bad.status_code == 401 and bad.json()["error_code"] == "INVALID_CREDENTIALS"
    assert client.get("/trackers").status_code == 401


def test_manual_tracker_creation_and_detail(client, alice):
    tracker = create_tracker(client, alice, habits=("A", "B"))
    assert tracker["status"] == "active" and tracker["days_elapsed"] == 1
    assert [h["name"] for h in tracker["habits"]] == ["A", "B"]
    listed = client.get("/trackers", headers=alice).json()
    assert [t["id"] for t in listed] == [tracker["id"]]
    upcoming = create_tracker(client, alice, name="Later", start_date=date.today() + timedelta(days=1))
    assert upcoming["status"] == "upcoming"


def test_progress_immutability_day_notes_and_history(client, alice):
    tracker = create_tracker(client, alice, start_date=date.today() - timedelta(days=2), habits=("A",))
    habit = tracker["habits"][0]["id"]
    today_index = 2

    ok = client.patch(f"/trackers/{tracker['id']}/progress", headers=alice,
                      json={"day_index": today_index, "habit_id": habit, "completed": True})
    assert ok.status_code == 200 and ok.json()["completed"] is True
    past = client.patch(f"/trackers/{tracker['id']}/progress", headers=alice,
                        json={"day_index": 0, "habit_id": habit, "completed": True})
    assert past.status_code == 409 and past.json()["error_code"] == "DAY_IMMUTABLE"

    detail = client.get(f"/trackers/{tracker['id']}", headers=alice).json()
    assert detail["history"]["last_archived_day"] == 1
    assert detail["completion_percent"] == round(1 / 3 * 100, 1)

    note = client.put(f"/trackers/{tracker['id']}/notes/{today_index}", headers=alice, json={"content": "Good day"})
    assert note.status_code == 200 and note.json()["day_notes"] == {"2": "Good day"}


def test_dashboard_trash_and_notes(client, alice):
    tracker = create_tracker(client, alice)
    client.post("/notes", headers=alice, json={"title": "Hello", "content": "World"})
    stats = client.get("/dashboard", headers=alice).json()
    assert stats["active_trackers"] == 1 and stats["total_notes"] == 1

    assert client.delete(f"/trackers/{tracker['id']}", headers=alice).status_code == 204
    trash = client.get("/trash", headers=alice).json()
    assert [t["id"] for t in trash["trackers"]] == [tracker["id"]]
    assert client.post(f"/trash/trackers/{tracker['id']}/restore", headers=alice).status_code == 200
    assert client.get(f"/trackers/{tracker['id']}", headers=alice).status_code == 200


def test_ownership_on_existing_endpoints(client, alice, bob):
    tracker = create_tracker(client, alice)
    assert client.get(f"/trackers/{tracker['id']}", headers=bob).status_code == 404


def test_validation_errors_keep_detail_and_add_standard_fields(client, alice):
    response = client.post("/trackers", headers=alice, json={"name": "", "duration_days": 0})
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR" and body["success"] is False
    assert isinstance(body["detail"], list) and body["detail"]
    assert body["message"]
