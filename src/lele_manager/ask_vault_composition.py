"""Explicit local-only composition for optional Ask-this-Vault synthesis."""

from __future__ import annotations

import math
import os

from lele_manager.application.ask_vault import (
    AskVaultProviderUnavailableError,
    AskVaultSynthesizer,
)


def resolve_ask_vault_synthesizer() -> AskVaultSynthesizer | None:
    """Build only an explicitly enabled local Ollama provider, without inference.

    An absent provider disables synthesis, regardless of other configuration.
    No optional dependency is imported until enabled configuration is valid.
    Dependency/version and construction failures are deliberately redacted.
    """

    provider = os.getenv("LELE_ASK_VAULT_PROVIDER")
    if provider is None:
        return None

    unavailable = "Ask-this-Vault synthesis provider is unavailable."
    model = os.getenv("LELE_ASK_VAULT_MODEL", "").strip()
    if provider != "ollama" or not model:
        raise AskVaultProviderUnavailableError(unavailable)

    try:
        timeout = float(os.getenv("LELE_ASK_VAULT_TIMEOUT_SECONDS", "120.0"))
    except ValueError:
        raise AskVaultProviderUnavailableError(unavailable) from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise AskVaultProviderUnavailableError(unavailable)

    try:
        from giadaware_ai.backends import OllamaBackend

        from lele_manager.adapters.giadaware_ai_ask_vault import (
            GiadaWareAIAskVaultSynthesizer,
        )

        return GiadaWareAIAskVaultSynthesizer(
            OllamaBackend(
                model=model,
                base_url="http://127.0.0.1:11434",
                timeout=timeout,
            )
        )
    except Exception:
        # The optional experimental dependency can fail during import or
        # construction (including incompatible public APIs). Never expose its
        # diagnostics or attempt another provider/model.
        raise AskVaultProviderUnavailableError(unavailable) from None
