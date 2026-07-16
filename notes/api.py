from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from users.dependencies import get_current_user
from .schema import NoteCreate, NoteUpdate, NoteResponse
from .service import NoteService

notes_router = APIRouter(prefix="/notes", tags=["Notes"])


@notes_router.get("", response_model=list[NoteResponse])
def list_notes(
    search: str | None = Query(None),
    archived: bool = Query(False),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return NoteService(db).list_notes(current_user.id, search=search, archived=archived)


@notes_router.post("", response_model=NoteResponse, status_code=201)
def create_note(data: NoteCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return NoteService(db).create(current_user.id, data)


@notes_router.patch("/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, data: NoteUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return NoteService(db).update(note_id, current_user.id, data)


@notes_router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    NoteService(db).delete(note_id, current_user.id)
