from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from notes.models import Note
from trackers.models import Tracker
from .schema import TrashedItem, TrashResponse
from utils.exceptions import AppException


class TrashService:
    def __init__(self, db: Session):
        self.db = db

    def get_trash(self, user_id: int) -> TrashResponse:
        trashed_notes = self.db.scalars(
            select(Note).where(
                Note.user_id == user_id,
                Note.is_active == False,
            ).order_by(Note.updated_at.desc())
        ).all()

        trashed_trackers = self.db.scalars(
            select(Tracker).where(
                Tracker.user_id == user_id,
                Tracker.is_active == False,
            ).order_by(Tracker.updated_at.desc())
        ).all()

        note_items = [
            TrashedItem(id=n.id, type="note", title=n.title, deleted_at=n.deleted_at or n.updated_at)
            for n in trashed_notes
        ]
        tracker_items = [
            TrashedItem(id=t.id, type="tracker", title=t.name, deleted_at=t.deleted_at or t.updated_at)
            for t in trashed_trackers
        ]

        return TrashResponse(
            notes=note_items,
            trackers=tracker_items,
            total=len(note_items) + len(tracker_items),
        )

    def restore_note(self, note_id: int, user_id: int) -> None:
        note = self.db.scalar(
            select(Note).where(Note.id == note_id, Note.user_id == user_id, Note.is_active == False)
        )
        if not note:
            raise AppException("Note not found in trash", status_code=404, error_code="NOT_FOUND")
        note.is_active = True
        note.deleted_at = None
        self.db.commit()

    def restore_tracker(self, tracker_id: int, user_id: int) -> None:
        tracker = self.db.scalar(
            select(Tracker).where(Tracker.id == tracker_id, Tracker.user_id == user_id, Tracker.is_active == False)
        )
        if not tracker:
            raise AppException("Tracker not found in trash", status_code=404, error_code="NOT_FOUND")
        tracker.is_active = True
        tracker.deleted_at = None
        self.db.commit()

    def delete_note_permanently(self, note_id: int, user_id: int) -> None:
        note = self.db.scalar(
            select(Note).where(Note.id == note_id, Note.user_id == user_id, Note.is_active == False)
        )
        if not note:
            raise AppException("Note not found in trash", status_code=404, error_code="NOT_FOUND")
        self.db.delete(note)
        self.db.commit()

    def delete_tracker_permanently(self, tracker_id: int, user_id: int) -> None:
        tracker = self.db.scalar(
            select(Tracker).where(Tracker.id == tracker_id, Tracker.user_id == user_id, Tracker.is_active == False)
        )
        if not tracker:
            raise AppException("Tracker not found in trash", status_code=404, error_code="NOT_FOUND")
        self.db.delete(tracker)
        self.db.commit()

    def empty_trash(self, user_id: int) -> int:
        trashed_notes = self.db.scalars(
            select(Note).where(Note.user_id == user_id, Note.is_active == False)
        ).all()
        trashed_trackers = self.db.scalars(
            select(Tracker).where(Tracker.user_id == user_id, Tracker.is_active == False)
        ).all()

        count = len(trashed_notes) + len(trashed_trackers)
        for n in trashed_notes:
            self.db.delete(n)
        for t in trashed_trackers:
            self.db.delete(t)
        self.db.commit()
        return count
