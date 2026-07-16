from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from users.dependencies import get_current_user
from .schema import TrackerCreate, TrackerUpdate, TrackerSummary, TrackerDetail, ProgressUpdate, ProgressResponse
from .service import TrackerService
from .models import TrackerStatus

trackers_router = APIRouter(prefix="/trackers", tags=["Trackers"])


@trackers_router.get("", response_model=list[TrackerSummary])
def list_trackers(
    status: TrackerStatus | None = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TrackerService(db).list_trackers(current_user.id, status=status)


@trackers_router.post("", response_model=TrackerDetail, status_code=201)
def create_tracker(data: TrackerCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = TrackerService(db)
    tracker = svc.create(current_user.id, data)
    return svc.get_detail(tracker.id, current_user.id)


@trackers_router.get("/{tracker_id}", response_model=TrackerDetail)
def get_tracker(tracker_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return TrackerService(db).get_detail(tracker_id, current_user.id)


@trackers_router.patch("/{tracker_id}", response_model=TrackerDetail)
def update_tracker(tracker_id: int, data: TrackerUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = TrackerService(db)
    svc.update(tracker_id, current_user.id, data)
    return svc.get_detail(tracker_id, current_user.id)


@trackers_router.delete("/{tracker_id}", status_code=204)
def delete_tracker(tracker_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    TrackerService(db).delete(tracker_id, current_user.id)


@trackers_router.patch("/{tracker_id}/pin", response_model=TrackerDetail)
def toggle_pin(tracker_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = TrackerService(db)
    tracker = svc.repo.get_by_id(tracker_id, current_user.id)
    if not tracker:
        from utils.exceptions import AppException
        raise AppException("Tracker not found", status_code=404, error_code="TRACKER_NOT_FOUND")
    tracker.is_pinned = not tracker.is_pinned
    svc.repo.update(tracker)
    return svc.get_detail(tracker_id, current_user.id)


@trackers_router.patch("/{tracker_id}/progress", response_model=ProgressResponse)
def update_progress(
    tracker_id: int,
    data: ProgressUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    progress = TrackerService(db).update_progress(
        tracker_id, current_user.id, data.day_index, data.habit_id, data.completed
    )
    return ProgressResponse(day_index=progress.day_index, habit_id=progress.habit_id, completed=progress.completed)
