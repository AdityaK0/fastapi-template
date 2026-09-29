"""Builds the configured AIProvider. Used as a FastAPI dependency so tests can swap it."""
from functools import lru_cache

from config import settings
from utils.exceptions import AppException

from .base import AIProvider


@lru_cache(maxsize=1)
def _build_provider() -> AIProvider:
    if settings.AI_PROVIDER == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            effort=settings.AI_EFFORT,
            temperature=settings.AI_TEMPERATURE,
            refusal_fallback=settings.AI_REFUSAL_FALLBACK,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
    raise AppException(f"Unknown AI provider '{settings.AI_PROVIDER}'", status_code=503, error_code="AI_NOT_CONFIGURED")


def get_ai_provider() -> AIProvider:
    if not settings.ai_enabled:
        raise AppException(
            "The AI assistant isn't set up on this server.",
            status_code=503,
            error_code="AI_NOT_CONFIGURED",
        )
    return _build_provider()
