"""Production composition boundary for factual verification.

Factual verification is disabled unless a provider is selected explicitly.
This module deliberately provides no implicit provider, fallback, or network
access. A concrete evidence provider must be introduced separately.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from lele_manager.adapters.openai_factual_verification import (
    OpenAIClaimExtractor,
    OpenAIEvidenceAssessor,
    OpenAIEvidenceRetriever,
)
from lele_manager.application.factual_verification import (
    FactualVerificationService,
)
from lele_manager.core.factual_verification_store import (
    FactualVerificationStore,
)


FACTUAL_VERIFICATION_PROVIDER_ENV = (
    "LELE_FACTUAL_VERIFICATION_PROVIDER"
)
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


class FactualVerificationConfigurationError(RuntimeError):
    """Raised when factual-verification runtime configuration is invalid."""


def _build_external_runtime(
    *,
    provider: str,
    api_key: str,
    store: FactualVerificationStore,
) -> FactualVerificationService:
    """Compose one explicitly selected external factual-verification runtime."""

    if provider != "openai":
        raise FactualVerificationConfigurationError(
            f"unsupported factual-verification provider: {provider}"
        )

    return FactualVerificationService(
        extractor=OpenAIClaimExtractor(api_key=api_key),
        retriever=OpenAIEvidenceRetriever(api_key=api_key),
        assessor=OpenAIEvidenceAssessor(api_key=api_key),
        store=store,
        now=lambda: datetime.now(timezone.utc),
    )


def resolve_factual_verification_runtime(
    *,
    store: FactualVerificationStore | None = None,
) -> FactualVerificationService | None:
    """Resolve the explicitly configured factual-verification runtime.

    Missing, blank, or ``disabled`` configuration means the capability is
    disabled. Unknown providers fail closed. No fallback is attempted.
    """

    raw_provider = os.getenv(FACTUAL_VERIFICATION_PROVIDER_ENV)

    if raw_provider is None:
        return None

    provider = raw_provider.strip().lower()

    if not provider or provider == "disabled":
        return None

    if provider == "openai":
        raise FactualVerificationConfigurationError(
            "OpenAI factual verification is not yet qualified "
            "for production use"
        )

    raise FactualVerificationConfigurationError(
        f"unsupported factual-verification provider: {provider}"
    )
