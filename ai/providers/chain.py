"""Automatic provider fallback (OpenCluely's ``later_feature.txt`` headline).

Tries each configured provider in priority order. Any provider error (busy,
timeout, bad key, over-long prompt, ...) moves on to the next one; the request
only fails when every provider has been tried. A successful completion returns
the model/usage of whichever provider actually served it.
"""
from __future__ import annotations

import logging

from .base import AIProvider, AIProviderError, Completion, CompletionRequest

logger = logging.getLogger(__name__)


class FallbackProvider(AIProvider):
    name = "fallback"

    def __init__(self, providers: list[AIProvider]):
        if not providers:
            raise ValueError("FallbackProvider needs at least one provider")
        self._providers = list(providers)
        self.model = providers[0].model

    @property
    def providers(self) -> list[AIProvider]:
        return list(self._providers)

    def complete(self, request: CompletionRequest) -> Completion:
        last_error: AIProviderError | None = None
        for index, provider in enumerate(self._providers):
            try:
                return provider.complete(request)
            except AIProviderError as exc:
                last_error = exc
                remaining = len(self._providers) - index - 1
                if remaining:
                    logger.warning(
                        "AI provider %s failed (%s); falling back to the next of %d remaining",
                        provider.name, type(exc).__name__, remaining,
                    )
        assert last_error is not None  # loop only exits empty if there were no providers
        raise last_error
