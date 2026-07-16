from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from users.dependencies import get_current_user
from .service import TrashService
from .schema import TrashResponse

trash_router = APIRouter(prefix="/trash", tags=["Trash"])


@trash_router.get("", response_model=TrashResponse)
def get_trash(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return TrashService(db).get_trash(current_user.id)


@trash_router.post("/notes/{note_id}/restore", status_code=200)
def restore_note(note_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    TrashService(db).restore_note(note_id, current_user.id)
    return {"message": "Note restored"}


@trash_router.post("/trackers/{tracker_id}/restore", status_code=200)
def restore_tracker(tracker_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    TrashService(db).restore_tracker(tracker_id, current_user.id)
    return {"message": "Tracker restored"}


@trash_router.delete("/notes/{note_id}", status_code=204)
def permanently_delete_note(note_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    TrashService(db).delete_note_permanently(note_id, current_user.id)


@trash_router.delete("/trackers/{tracker_id}", status_code=204)
def permanently_delete_tracker(tracker_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    TrashService(db).delete_tracker_permanently(tracker_id, current_user.id)


@trash_router.delete("", status_code=200)
def empty_trash(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    count = TrashService(db).empty_trash(current_user.id)
    return {"message": f"Permanently deleted {count} items", "count": count}
