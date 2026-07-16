from sqlalchemy.orm import Session

from .models import Note
from .repository import NoteRepository
from utils.exceptions import AppException


class NoteService:
    def __init__(self, db: Session):
        self.repo = NoteRepository(db)

    def create(self, user_id: int, data) -> Note:
        note = Note(user_id=user_id, title=data.title, content=data.content)
        return self.repo.create(note)

    def list_notes(self, user_id: int, search: str | None = None, archived: bool = False) -> list[Note]:
        return self.repo.get_all(user_id, search=search, archived=archived)

    def get_or_404(self, note_id: int, user_id: int) -> Note:
        note = self.repo.get_by_id(note_id, user_id)
        if not note:
            raise AppException("Note not found", status_code=404, error_code="NOTE_NOT_FOUND")
        return note

    def update(self, note_id: int, user_id: int, data) -> Note:
        note = self.get_or_404(note_id, user_id)
        if data.title is not None:
            note.title = data.title
        if data.content is not None:
            note.content = data.content
        if data.is_pinned is not None:
            note.is_pinned = data.is_pinned
        if data.is_archived is not None:
            note.is_archived = data.is_archived
        return self.repo.update(note)

    def delete(self, note_id: int, user_id: int) -> None:
        note = self.get_or_404(note_id, user_id)
        self.repo.delete(note)
