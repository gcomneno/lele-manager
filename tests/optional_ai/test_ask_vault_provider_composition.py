"""Opt-in composition contracts using the real optional API and fake backends."""

from __future__ import annotations

import builtins
import traceback
from unittest.mock import Mock

import pytest
from giadaware_ai import AIConfigurationError
from giadaware_ai import backends

from lele_manager import ask_vault_composition as composition
from lele_manager.adapters import giadaware_ai_ask_vault as adapter
from lele_manager.application.ask_vault import AskVaultProviderUnavailableError


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LELE_ASK_VAULT_PROVIDER",
        "LELE_ASK_VAULT_MODEL",
        "LELE_ASK_VAULT_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    # A missed mock must fail before it can construct a real provider.
    monkeypatch.setattr(backends, "OllamaBackend", Mock(side_effect=AssertionError))


@pytest.mark.parametrize("timeout", [None, "0.25", " 17.5 "])
def test_enabled_local_provider_has_exact_constructor_arguments(
    monkeypatch: pytest.MonkeyPatch,
    timeout: str | None,
) -> None:
    monkeypatch.setenv("LELE_ASK_VAULT_PROVIDER", "ollama")
    monkeypatch.setenv("LELE_ASK_VAULT_MODEL", "  synthetic:model \n")
    if timeout is not None:
        monkeypatch.setenv("LELE_ASK_VAULT_TIMEOUT_SECONDS", timeout)
    for name in ("LELE_ASK_VAULT_ENDPOINT", "LELE_ASK_VAULT_BASE_URL", "OLLAMA_HOST"):
        monkeypatch.setenv(name, "https://PRIVATE_CREDENTIAL@example.invalid")
    backend = Mock()
    constructor = Mock(return_value=backend)
    monkeypatch.setattr(backends, "OllamaBackend", constructor)
    result = composition.resolve_ask_vault_synthesizer()
    assert isinstance(result, adapter.GiadaWareAIAskVaultSynthesizer)
    constructor.assert_called_once_with(
        model="synthetic:model",
        base_url="http://127.0.0.1:11434",
        timeout=120.0 if timeout is None else float(timeout),
    )
    backend.generate_json.assert_not_called()


@pytest.mark.parametrize(
    "module",
    ["giadaware_ai.backends", "lele_manager.adapters.giadaware_ai_ask_vault"],
)
@pytest.mark.parametrize(
    "error", [ModuleNotFoundError, ImportError, AttributeError, TypeError, RuntimeError]
)
def test_optional_import_failures_and_incompatibility_are_redacted(
    monkeypatch: pytest.MonkeyPatch,
    module: str,
    error: type[Exception],
) -> None:
    monkeypatch.setenv("LELE_ASK_VAULT_PROVIDER", "ollama")
    monkeypatch.setenv("LELE_ASK_VAULT_MODEL", "model")
    original_import = builtins.__import__
    attempts = []

    def failing_import(name, *args, **kwargs):
        if name == module:
            attempts.append(name)
            raise error("PRIVATE_CREDENTIAL")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    with pytest.raises(AskVaultProviderUnavailableError) as caught:
        composition.resolve_ask_vault_synthesizer()
    assert attempts == [module]
    assert str(caught.value) == "Ask-this-Vault synthesis provider is unavailable."
    assert "PRIVATE_CREDENTIAL" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__
    backends.OllamaBackend.assert_not_called()


@pytest.mark.parametrize("stage", ["backend", "adapter"])
@pytest.mark.parametrize(
    "error", [AIConfigurationError, TypeError, ValueError, RuntimeError]
)
def test_construction_failure_is_redacted_without_retry_or_fallback(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    error: type[Exception],
) -> None:
    monkeypatch.setenv("LELE_ASK_VAULT_PROVIDER", "ollama")
    monkeypatch.setenv("LELE_ASK_VAULT_MODEL", "PRIVATE_MODEL")
    constructor = Mock(return_value=Mock())
    wrapper = Mock(return_value=Mock())
    failure = constructor if stage == "backend" else wrapper
    failure.side_effect = error("PRIVATE_CREDENTIAL")
    monkeypatch.setattr(backends, "OllamaBackend", constructor)
    monkeypatch.setattr(adapter, "GiadaWareAIAskVaultSynthesizer", wrapper)
    with pytest.raises(AskVaultProviderUnavailableError) as caught:
        composition.resolve_ask_vault_synthesizer()
    assert constructor.call_count == 1
    assert wrapper.call_count == (0 if stage == "backend" else 1)
    assert str(caught.value) == "Ask-this-Vault synthesis provider is unavailable."
    rendered = "".join(traceback.format_exception(caught.value))
    assert "PRIVATE_CREDENTIAL" not in rendered
    assert "PRIVATE_MODEL" not in rendered
    assert caught.value.__suppress_context__
