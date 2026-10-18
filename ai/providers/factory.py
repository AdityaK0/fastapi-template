"""Builds the configured AIProvider from the AI_PROVIDERS list.

Multiple providers are wrapped in a FallbackProvider so a failing provider
falls through to the next one. Used as a FastAPI dependency so tests can swap it.
"""
from functools import lru_cache

from config import settings
from utils.exceptions import AppException

from .base import AIProvider
from .chain import FallbackProvider
from .registry import FAMILY_ANTHROPIC, FAMILY_GOOGLE, FAMILY_OPENAI, ProviderEntry


def _build_one(entry: ProviderEntry) -> AIProvider:
    if entry.family == FAMILY_ANTHROPIC:
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=entry.api_key,
            model=entry.model,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            effort=settings.AI_EFFORT,
            temperature=settings.AI_TEMPERATURE,
            refusal_fallback=settings.AI_REFUSAL_FALLBACK,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
    if entry.family == FAMILY_GOOGLE:
        from .gemini_provider import GeminiProvider
        return GeminiProvider(
            api_key=entry.api_key,
            model=entry.model,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            temperature=settings.AI_TEMPERATURE,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
    if entry.family == FAMILY_OPENAI:
        from .openai_compatible_provider import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            api_key=entry.api_key,
            model=entry.model,
            base_url=entry.base_url,
            provider_id=entry.id,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            temperature=settings.AI_TEMPERATURE,
            extra_headers=entry.extra_headers,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
    raise AppException(
        f"AI provider family '{entry.family}' has no adapter.", status_code=503, error_code="AI_NOT_CONFIGURED"
    )


@lru_cache(maxsize=1)
def _build_provider() -> AIProvider:
    providers = [_build_one(entry) for entry in settings.ai_provider_entries]
    if not providers:
        raise AppException(
            "The AI assistant isn't set up on this server.", status_code=503, error_code="AI_NOT_CONFIGURED"
        )
    if len(providers) == 1 or not settings.AI_FALLBACK_ON_ERROR:
        return providers[0]
    return FallbackProvider(providers)


def get_ai_provider() -> AIProvider:
    if not settings.ai_enabled:
        raise AppException(
            "The AI assistant isn't set up on this server.",
            status_code=503,
            error_code="AI_NOT_CONFIGURED",
        )
    return _build_provider()
