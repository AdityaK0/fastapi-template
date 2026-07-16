from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from users.dependencies import get_current_user
from .service import DashboardService
from .schema import DashboardStats

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dashboard_router.get("", response_model=DashboardStats)
def get_dashboard(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return DashboardService(db).get_stats(current_user.id)
