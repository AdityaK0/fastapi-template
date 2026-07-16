from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from users.dependencies import get_current_user
from .service import ActivityService
from .schema import ActivityResponse

activity_router = APIRouter(prefix="/activity", tags=["Activity"])


@activity_router.get("", response_model=ActivityResponse)
def get_activity(
    start_date: Optional[date] = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    end_date:   Optional[date] = Query(None, description="Inclusive end date   (YYYY-MM-DD)"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return daily event counts for the authenticated user.

    Default range: Jan 1 of the current year → today.
    Response is suitable for rendering a GitHub-style activity heatmap.
    """
    return ActivityService(db).get_activity(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
    )
