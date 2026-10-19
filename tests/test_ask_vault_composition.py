"""Disabled and invalid composition is independent of optional AI packages."""

from __future__ import annotations

import builtins
import importlib
import traceback

import pytest

from lele_manager import ask_vault_composition as composition
from lele_manager.application.ask_vault import AskVaultProviderUnavailableError


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LELE_ASK_VAULT_PROVIDER",
        "LELE_ASK_VAULT_MODEL",
        "LELE_ASK_VAULT_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def block_optional_imports(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    original_import = builtins.__import__
    imports: list[str] = []

    def guarded_import(name, *args, **kwargs):
        if name.startswith("giadaware_ai") or name.endswith("giadaware_ai_ask_vault"):
            imports.append(name)
            raise AssertionError("Optional dependency must not be imported")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    return imports


@pytest.mark.parametrize("stray_configuration", [False, True])
def test_absent_provider_disables_without_optional_imports(
    monkeypatch: pytest.MonkeyPatch,
    stray_configuration: bool,
) -> None:
    if stray_configuration:
        monkeypatch.setenv("LELE_ASK_VAULT_MODEL", "model-is-not-opt-in")
        monkeypatch.setenv("LELE_ASK_VAULT_TIMEOUT_SECONDS", "invalid")
        monkeypatch.setenv("OLLAMA_MODEL", "implicit-model")
        monkeypatch.setenv("OPENAI_API_KEY", "PRIVATE_CREDENTIAL")
    imports = block_optional_imports(monkeypatch)
    importlib.reload(composition)
    assert composition.resolve_ask_vault_synthesizer() is None
    assert imports == []


@pytest.mark.parametrize(
    "configuration",
    [
        {"PROVIDER": provider, "MODEL": "model"}
        for provider in (
            "",
            " ",
            "disabled",
            "OLLAMA",
            " ollama ",
            "openai",
            "PRIVATE_CREDENTIAL",
        )
    ]
    + [
        {"PROVIDER": "ollama"},
        {"PROVIDER": "ollama", "MODEL": ""},
        {"PROVIDER": "ollama", "MODEL": " \t\n"},
    ]
    + [
        {"PROVIDER": "ollama", "MODEL": "model", "TIMEOUT_SECONDS": timeout}
        for timeout in (
            "",
            " ",
            "zero",
            "0",
            "-1",
            "nan",
            "inf",
            "-inf",
            "1e999",
            "PRIVATE_CREDENTIAL",
        )
    ],
)
def test_invalid_configuration_fails_before_imports_and_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    configuration: dict[str, str],
) -> None:
    for name, value in configuration.items():
        monkeypatch.setenv(f"LELE_ASK_VAULT_{name}", value)
    imports = block_optional_imports(monkeypatch)
    with pytest.raises(AskVaultProviderUnavailableError) as caught:
        composition.resolve_ask_vault_synthesizer()
    assert str(caught.value) == "Ask-this-Vault synthesis provider is unavailable."
    assert "PRIVATE_CREDENTIAL" not in "".join(traceback.format_exception(caught.value))
    assert imports == []
