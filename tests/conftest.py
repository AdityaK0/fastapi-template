import os
import sys
from pathlib import Path

os.environ["DEBUG"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import main  # noqa: E402  — imports every module, so all models are registered
from ai.providers.factory import get_ai_provider  # noqa: E402
from database import Base, get_db  # noqa: E402

from tests.fakes import ScriptedProvider  # noqa: E402


@pytest.fixture
def engine():
    # In-memory SQLite by default. Set TEST_DATABASE_URL to a throwaway PostgreSQL
    # database to run the same suite against Postgres (tables are dropped after each test).
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    if url:
        Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def db(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def provider():
    return ScriptedProvider()


@pytest.fixture
def client(session_factory, provider):
    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[get_db] = override_get_db
    main.app.dependency_overrides[get_ai_provider] = lambda: provider
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def register(client, username: str) -> dict:
    response = client.post("/auth/register", json={
        "username": username,
        "fullname": f"{username.title()} Tester",
        "email": f"{username}@example.com",
        "password": "password123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_tracker(client, headers, *, name="Morning Routine", habits=("Walk", "Read", "Water"),
                   duration_days=30, start_date: date | None = None) -> dict:
    response = client.post("/trackers", headers=headers, json={
        "name": name,
        "description": "Test tracker",
        "duration_days": duration_days,
        "start_date": (start_date or date.today()).isoformat(),
        "habits": [{"name": h, "position": i} for i, h in enumerate(habits)],
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def alice(client):
    return register(client, "alice")


@pytest.fixture
def bob(client):
    return register(client, "bob")


@pytest.fixture
def past_tracker(client, alice, db):
    """A tracker that started 13 days ago (day 14 is today) with seeded history."""
    from trackers.models import TrackerProgress

    tracker = create_tracker(client, alice, name="Fitness", habits=("Walk", "Stretch", "Water"),
                             start_date=date.today() - timedelta(days=13))
    walk, stretch, water = (h["id"] for h in tracker["habits"])
    rows = []
    for day in range(13):                  # finished days 0-12; today (13) untouched
        done = {walk, water}
        if day < 7 or day >= 11:
            done.add(stretch)              # every habit in week 1 and on days 11-12
        elif day in (8, 9):
            done = {walk}                  # the slump
        for habit_id in done:
            rows.append(TrackerProgress(tracker_id=tracker["id"], day_index=day, habit_id=habit_id, completed=True))
    db.add_all(rows)
    db.commit()
    return tracker
