import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from users.api import auth_router, user_router
from notes.api import notes_router
from trackers.api import trackers_router
from dashboard.api import dashboard_router
from trash.api import trash_router
from events.api import activity_router
from ai.api import ai_router, tracker_ai_router
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = jsonable_encoder(exc.errors())
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", ()) if p not in ("body", "query", "path"))
    message = first.get("msg", "Invalid request")
    # Keep FastAPI's `detail` list for existing clients; add the standard error fields.
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": f"{field}: {message}" if field else message,
            "error_code": "VALIDATION_ERROR",
            "detail": errors,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    logging.getLogger("app.db").exception("Database error on %s %s", request.method, request.url.path)
    return _error_response(500, "A database error occurred. Please try again.", "DATABASE_ERROR")


@app.get("/health")
def healthCheck():
    return {"message": "Habit Tracker API v2.0 is running"}


@app.on_event("startup")
def checker():
    try :
        print("holla")
    except Exception as e:
        raise e
        
    


        
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(notes_router)
app.include_router(trackers_router)
app.include_router(dashboard_router)
app.include_router(trash_router)
app.include_router(activity_router)
app.include_router(ai_router)
app.include_router(tracker_ai_router)
