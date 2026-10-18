"""Provider catalog and .env parsing for multi-provider AI configuration.

Inspired by OpenCluely's ``ai/providers.js``: every provider is described by an
id, a label, a *family* (which adapter talks to it) and a base URL / auth shape.
The family decides the wire format, because the APIs genuinely differ:

    ``anthropic``  Anthropic Messages API (official SDK)
    ``google``     Gemini generateContent (official SDK)
    ``openai``     OpenAI-compatible ``POST {base_url}/chat/completions`` (REST)

Providers are declared in the ``AI_PROVIDERS`` environment variable as a
pipe-delimited list, in priority order (first = primary, the rest are fallbacks)::

    AI_PROVIDERS=openrouter|openai/gpt-4o-mini|env:OPENROUTER_API_KEY
                 gemini|gemini-3-pro|env:GEMINI_API_KEY
                 openai|gpt-4o|sk-...

Each entry is ``id | model | api_key | base_url`` (the last two are optional):
  * ``id``       a known id from PROVIDER_CATALOG (unknown ids need a base_url)
  * ``model``    the model to call; empty = the provider's default model
  * ``api_key``  the key, or ``env:NAME`` to read it from another env var;
                 empty = try the provider's conventional env var (e.g. OPENROUTER_API_KEY)
  * ``base_url`` override the catalog base URL (required for custom providers)
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

FAMILY_ANTHROPIC = "anthropic"
FAMILY_GOOGLE = "google"
FAMILY_OPENAI = "openai"


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    label: str
    family: str
    base_url: str
    default_model: str
    env_key: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)


# Known providers, mirroring OpenCluely's registry. Any OpenAI-compatible
# endpoint can be added without a code change by giving an unknown id a base_url.
PROVIDER_CATALOG: dict[str, ProviderDefinition] = {
    "anthropic": ProviderDefinition(
        "anthropic", "Anthropic (Claude)", FAMILY_ANTHROPIC,
        "https://api.anthropic.com/v1", "claude-opus-5", "ANTHROPIC_API_KEY",
    ),
    "gemini": ProviderDefinition(
        "gemini", "Google Gemini", FAMILY_GOOGLE,
        "https://generativelanguage.googleapis.com/v1beta", "gemini-3.5-flash", "GEMINI_API_KEY",
    ),
    "openai": ProviderDefinition(
        "openai", "OpenAI", FAMILY_OPENAI,
        "https://api.openai.com/v1", "gpt-4o", "OPENAI_API_KEY",
    ),
    "openrouter": ProviderDefinition(
        "openrouter", "OpenRouter", FAMILY_OPENAI,
        "https://openrouter.ai/api/v1", "openai/gpt-4o-mini", "OPENROUTER_API_KEY",
        {"HTTP-Referer": "https://localhost", "X-Title": "Habbit Tracker"},
    ),
    "groq": ProviderDefinition(
        "groq", "Groq", FAMILY_OPENAI,
        "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY",
    ),
    "mistral": ProviderDefinition(
        "mistral", "Mistral AI", FAMILY_OPENAI,
        "https://api.mistral.ai/v1", "mistral-large-latest", "MISTRAL_API_KEY",
    ),
    "qwen": ProviderDefinition(
        "qwen", "Qwen", FAMILY_OPENAI,
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-max", "DASHSCOPE_API_KEY",
    ),
    "grok": ProviderDefinition(
        "grok", "Grok", FAMILY_OPENAI,
        "https://api.x.ai/v1", "grok-4", "XAI_API_KEY",
    ),
    "nvidia": ProviderDefinition(
        "nvidia", "NVIDIA NIM", FAMILY_OPENAI,
        "https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct", "NVIDIA_API_KEY",
    ),
    "deepseek": ProviderDefinition(
        "deepseek", "DeepSeek", FAMILY_OPENAI,
        "https://api.deepseek.com/v1", "deepseek-chat", "DEEPSEEK_API_KEY",
    ),
}

# "google" is the family name OpenCluely uses; accept it as an alias for gemini.
_ALIASES = {"google": "gemini"}

_SPLIT_ENTRIES = re.compile(r"[\n;,]+")


@dataclass(frozen=True)
class ProviderEntry:
    """One resolved provider configuration, ready to build an adapter from."""
    id: str
    label: str
    family: str
    model: str
    api_key: str
    base_url: str
    extra_headers: dict[str, str] = field(default_factory=dict)


def get_definition(provider_id: str) -> ProviderDefinition | None:
    return PROVIDER_CATALOG.get(_ALIASES.get(provider_id, provider_id))


def resolve_secret(value: str | None) -> str:
    """A literal key, or ``env:NAME`` read from the environment."""
    if not value:
        return ""
    value = value.strip()
    if value.startswith("env:"):
        return os.environ.get(value[4:].strip(), "").strip()
    return value


def parse_provider_entries(
    raw: str | None,
    *,
    legacy_provider: str | None = None,
    legacy_key: str | None = None,
    legacy_model: str | None = None,
) -> list[ProviderEntry]:
    """Resolve AI_PROVIDERS, falling back to the single-provider settings."""
    entries: list[ProviderEntry] = []
    for chunk in _SPLIT_ENTRIES.split(raw or ""):
        chunk = chunk.strip()
        if not chunk or chunk.startswith("#"):
            continue
        parts = [part.strip() for part in chunk.split("|")]
        provider_id = parts[0].lower() if parts and parts[0] else ""
        if not provider_id:
            continue

        definition = get_definition(provider_id)
        model = parts[1] if len(parts) > 1 else ""
        secret = parts[2] if len(parts) > 2 else ""
        base_url = parts[3] if len(parts) > 3 else ""

        if definition is None and not base_url:
            logger.warning("AI provider '%s' is unknown and has no base_url; skipping it.", provider_id)
            continue
        if not model and not (definition and definition.default_model):
            logger.warning("AI provider '%s' has no model and no known default; skipping it.", provider_id)
            continue

        api_key = resolve_secret(secret) or resolve_secret(definition.env_key if definition else None)
        if not api_key:
            logger.warning("AI provider '%s' has no API key; skipping it.", provider_id)
            continue

        entries.append(ProviderEntry(
            id=provider_id,
            label=definition.label if definition else provider_id,
            family=definition.family if definition else FAMILY_OPENAI,
            model=model or (definition.default_model if definition else ""),
            api_key=api_key,
            base_url=(base_url or (definition.base_url if definition else "")).rstrip("/"),
            extra_headers=dict(definition.extra_headers) if definition else {},
        ))

    if not entries and legacy_provider and legacy_provider != "disabled":
        definition = get_definition(legacy_provider)
        api_key = resolve_secret(legacy_key) or resolve_secret(definition.env_key if definition else None)
        if definition and api_key and (legacy_model or definition.default_model):
            entries.append(ProviderEntry(
                id=definition.id,
                label=definition.label,
                family=definition.family,
                model=legacy_model or definition.default_model,
                api_key=api_key,
                base_url=definition.base_url.rstrip("/"),
                extra_headers=dict(definition.extra_headers),
            ))

    return entries
