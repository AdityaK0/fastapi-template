import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from users.api import user_router
from utils.exceptions import AppException
from middleware.request_logging import RequestLoggingMiddleware
from middleware.security import SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="FastAPI Template",
    description="Production-ready FastAPI backend — session auth, RBAC, layered architecture.",
    version="1.0.0",
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


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
    return {"message": "FastAPI template is running"}


# Add your routers below
app.include_router(user_router)
