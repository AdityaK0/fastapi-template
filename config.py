from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    DATABASE_URL: str
    APP_ENV: str = "development"
    JWT_SECRET_KEY: str = "fallback-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:5173"

    
    GOOGLE_AUTH_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_REDIRECT_URL: str = "http://localhost:8001/auth/google/callback"
    GOOGLE_TOKEN_EXCHANGE_URL: str = "https://oauth2.googleapis.com/token"
    GOOGLE_USER_INFO_URL: str = "https://www.googleapis.com/oauth2/v3/userinfo"
    GOOGLE_PUBLIC_KEY_URL: str = "https://www.googleapis.com/oauth2/v3/certs"
    GOOGLE_CLIENT_ID :str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET :str = os.getenv("GOOGLE_CLIENT_SECRET")
    

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
