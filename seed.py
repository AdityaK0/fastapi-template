"""Seed script: creates demo user + sample notes + trackers."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, timedelta
from database import SessionLocal, engine, Base
from users.models import User, Role, Permission, user_roles, role_permissions
from notes.models import Note
from trackers.models import Tracker, TrackerHabit, TrackerProgress, TrackerStatus
from utils.security import hash_password


def seed():
    db = SessionLocal()
    try:
        # Create demo user
        user = db.query(User).filter_by(username="demo").first()
        if not user:
            user = User(
                username="demo",
                fullname="Demo User",
                email="demo@example.com",
                hashed_password=hash_password("password123"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created user: demo / password123")

        # Sample notes
        existing_notes = db.query(Note).filter_by(user_id=user.id).count()
        if existing_notes == 0:
            notes = [
                Note(user_id=user.id, title="Welcome to Habit Tracker!", content="Start building good habits today. Create your first tracker from the dashboard.", is_pinned=True),
                Note(user_id=user.id, title="75 Hard Rules", content="1. Follow a diet\n2. Two 45-min workouts\n3. Drink 1 gallon water\n4. Read 10 pages\n5. Take a progress photo"),
                Note(user_id=user.id, title="Morning Routine Tips", content="Wake up at the same time every day. Avoid phone for first 30 minutes. Drink water before coffee."),
            ]
            db.add_all(notes)
            db.commit()
            print("Created sample notes")

        # Sample tracker
        existing_trackers = db.query(Tracker).filter_by(user_id=user.id).count()
        if existing_trackers == 0:
            today = date.today()
            start = today - timedelta(days=10)
            tracker = Tracker(
                user_id=user.id,
                name="Morning Routine",
                description="Building a consistent morning routine for 30 days",
                duration_days=30,
                start_date=start,
                end_date=start + timedelta(days=29),
                status=TrackerStatus.active,
            )
            db.add(tracker)
            db.commit()
            db.refresh(tracker)

            habit_names = ["Wake up before 7AM", "Morning run", "Read a chapter", "Meditate 10 min"]
            habits = [TrackerHabit(tracker_id=tracker.id, name=n, position=i) for i, n in enumerate(habit_names)]
            db.add_all(habits)
            db.commit()
            for h in habits:
                db.refresh(h)

            # Add some progress data
            import random
            random.seed(42)
            progress_items = []
            for day_idx in range(11):
                for habit in habits:
                    if random.random() > 0.3:
                        progress_items.append(TrackerProgress(
                            tracker_id=tracker.id,
                            day_index=day_idx,
                            habit_id=habit.id,
                            completed=True,
                        ))
            db.add_all(progress_items)
            db.commit()
            print("Created sample tracker with progress")

        print("Seed complete!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
