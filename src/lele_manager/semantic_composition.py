"""Optional semantic-extraction runtime composition for TritaLeLe.

The deterministic product must remain importable and usable without
GiadaWare AI.  Semantic extraction is therefore composed lazily and only after
an explicit local provider configuration is present.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os

from lele_manager.application.semantic_lesson_extraction import (
    SemanticLessonExtractor,
)


SEMANTIC_PROVIDER_ENV = "LELE_SEMANTIC_PROVIDER"
SEMANTIC_MODEL_ENV = "LELE_SEMANTIC_MODEL"

_LOCAL_PROVIDER = "ollama"
_LOCAL_ENDPOINT = "http://127.0.0.1:11434"
_STRATEGY = "semantic"


class SemanticRuntimeConfigurationError(Exception):
    """Semantic runtime configuration is present but invalid."""


class SemanticRuntimeDependencyError(Exception):
    """The optional GiadaWare AI dependency is unavailable."""


@dataclass(frozen=True, slots=True)
class SemanticRuntime:
    """Resolved optional semantic extraction composition."""

    extractor: SemanticLessonExtractor
    strategy: str
    provider: str
    model: str
    locality: str
    endpoint: str

    @property
    def extraction_metadata(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "provider": self.provider,
            "model": self.model,
            "locality": self.locality,
            "endpoint": self.endpoint,
        }


def resolve_semantic_runtime(
    environment: Mapping[str, str] | None = None,
) -> SemanticRuntime | None:
    """Resolve the explicitly configured local semantic runtime.

    Missing ``LELE_SEMANTIC_PROVIDER`` means semantic extraction is disabled.
    No provider fallback or automatic remote routing is performed.
    """

    env = os.environ if environment is None else environment
    raw_provider = env.get(SEMANTIC_PROVIDER_ENV)
    if raw_provider is None:
        return None

    provider = raw_provider.strip().lower()
    if not provider:
        raise SemanticRuntimeConfigurationError(
            f"{SEMANTIC_PROVIDER_ENV} must not be empty"
        )
    if provider != _LOCAL_PROVIDER:
        raise SemanticRuntimeConfigurationError(
            f"{SEMANTIC_PROVIDER_ENV} must be {_LOCAL_PROVIDER!r}"
        )

    raw_model = env.get(SEMANTIC_MODEL_ENV)
    if raw_model is None or not raw_model.strip():
        raise SemanticRuntimeConfigurationError(
            f"{SEMANTIC_MODEL_ENV} is required when semantic extraction is enabled"
        )
    model = raw_model.strip()

    try:
        from giadaware_ai.backends import OllamaBackend

        from lele_manager.adapters.giadaware_ai_semantic_extraction import (
            ExtractLessonCandidatesCapability,
        )
    except ModuleNotFoundError as exc:
        if exc.name == "giadaware_ai" or (
            exc.name is not None and exc.name.startswith("giadaware_ai.")
        ):
            raise SemanticRuntimeDependencyError(
                "GiadaWare AI is not installed"
            ) from None
        raise

    try:
        backend = OllamaBackend(
            model=model,
            base_url=_LOCAL_ENDPOINT,
        )
    except Exception as exc:
        try:
            from giadaware_ai import AIConfigurationError
        except ModuleNotFoundError:
            raise
        if isinstance(exc, AIConfigurationError):
            raise SemanticRuntimeConfigurationError(
                "semantic backend configuration is invalid"
            ) from None
        raise

    return SemanticRuntime(
        extractor=ExtractLessonCandidatesCapability(backend),
        strategy=_STRATEGY,
        provider=_LOCAL_PROVIDER,
        model=model,
        locality="local",
        endpoint=_LOCAL_ENDPOINT,
    )
