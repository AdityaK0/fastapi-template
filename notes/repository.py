from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from .models import Note


class NoteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, note: Note) -> Note:
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_by_id(self, note_id: int, user_id: int) -> Note | None:
        return self.db.scalar(
            select(Note).where(Note.id == note_id, Note.user_id == user_id, Note.is_active == True)
        )

    def get_all(self, user_id: int, search: str | None = None, archived: bool = False) -> list[Note]:
        q = select(Note).where(Note.user_id == user_id, Note.is_active == True, Note.is_archived == archived)
        if search:
            q = q.where(or_(Note.title.ilike(f"%{search}%"), Note.content.ilike(f"%{search}%")))
        q = q.order_by(Note.is_pinned.desc(), Note.updated_at.desc())
        return list(self.db.scalars(q).all())

    def update(self, note: Note) -> Note:
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete(self, note: Note) -> None:
        from datetime import datetime
        note.is_active = False
        note.deleted_at = datetime.now()
        self.db.commit()
