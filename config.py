from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Falls back to a local SQLite file when DATABASE_URL isn't set
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'app.db'}"
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
    # Optional — Google login only works when both are set
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # AI assistant. Off until AI_API_KEY is set; the key is only ever used server-side.
    AI_PROVIDER: str = "anthropic"            # "anthropic" or "disabled"
    AI_API_KEY: str | None = None
    AI_MODEL: str = "claude-opus-5"
    AI_MAX_OUTPUT_TOKENS: int = 16000         # per model call, thinking included
    AI_EFFORT: str | None = None              # low | medium | high | xhigh | max; unset = model default
    # Only for models that still accept sampling parameters (Opus 4.7+ rejects them).
    AI_TEMPERATURE: float | None = None
    AI_REFUSAL_FALLBACK: bool = True          # server-side fallback model on a safety refusal
    AI_REQUEST_TIMEOUT_SECONDS: float = 60.0
    AI_MAX_RETRIES: int = 2
    AI_MAX_TOOL_ROUNDS: int = 6               # model calls per user message
    AI_CONTEXT_MAX_MESSAGES: int = 20         # stored messages replayed to the model
    AI_MAX_MESSAGE_CHARS: int = 2000
    AI_MAX_TURNS_PER_CONVERSATION: int = 60
    AI_RATE_LIMIT_PER_MINUTE: int = 8
    AI_RATE_LIMIT_PER_DAY: int = 200

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def ai_enabled(self) -> bool:
        return self.AI_PROVIDER != "disabled" and bool(self.AI_API_KEY)


settings = Settings()
