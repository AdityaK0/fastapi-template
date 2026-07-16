import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from users.api import auth_router, user_router
from notes.api import notes_router
from trackers.api import trackers_router
from dashboard.api import dashboard_router
from trash.api import trash_router
from utils.exceptions import AppException
from middleware.request_logging import RequestLoggingMiddleware
from middleware.security import SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Habit Tracker & Notes API",
    description="Full-stack habit tracker with notes, JWT authentication, and RBAC.",
    version="2.0.0",
)

uploads_dir = Path(__file__).resolve().parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, message: str, error_code: str):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "error_code": error_code},
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return _error_response(exc.status_code, exc.message, exc.error_code or "APP_ERROR")


@app.get("/")
def root():
    return {"message": "Habit Tracker API v2.0 is running"}


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(notes_router)
app.include_router(trackers_router)
app.include_router(dashboard_router)
app.include_router(trash_router)
