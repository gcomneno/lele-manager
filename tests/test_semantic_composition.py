from __future__ import annotations

import builtins
from collections.abc import Mapping
from types import ModuleType
from unittest.mock import patch

import pytest

from lele_manager.semantic_composition import (
    SEMANTIC_MODEL_ENV,
    SEMANTIC_PROVIDER_ENV,
    SemanticRuntimeConfigurationError,
    SemanticRuntimeDependencyError,
    resolve_semantic_runtime,
)


def test_semantic_runtime_is_disabled_when_provider_is_absent() -> None:
    assert resolve_semantic_runtime({}) is None
    assert (
        resolve_semantic_runtime({SEMANTIC_MODEL_ENV: "configured-but-disabled"})
        is None
    )


@pytest.mark.parametrize(
    "environment",
    [
        {SEMANTIC_PROVIDER_ENV: ""},
        {SEMANTIC_PROVIDER_ENV: "   "},
        {SEMANTIC_PROVIDER_ENV: "openai", SEMANTIC_MODEL_ENV: "gpt"},
        {SEMANTIC_PROVIDER_ENV: "deepseek", SEMANTIC_MODEL_ENV: "model"},
        {SEMANTIC_PROVIDER_ENV: "ollama"},
        {SEMANTIC_PROVIDER_ENV: "ollama", SEMANTIC_MODEL_ENV: ""},
        {SEMANTIC_PROVIDER_ENV: "ollama", SEMANTIC_MODEL_ENV: "   "},
    ],
)
def test_invalid_semantic_configuration_fails_closed(
    environment: Mapping[str, str],
) -> None:
    with pytest.raises(SemanticRuntimeConfigurationError):
        resolve_semantic_runtime(environment)


def test_missing_optional_giadaware_ai_dependency_is_controlled() -> None:
    real_import = builtins.__import__

    def blocked_import(
        name: str,
        globals: object = None,
        locals: object = None,
        fromlist: object = (),
        level: int = 0,
    ) -> ModuleType:
        if name == "giadaware_ai" or name.startswith("giadaware_ai."):
            error = ModuleNotFoundError("No module named 'giadaware_ai'")
            error.name = "giadaware_ai"
            raise error
        return real_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    with patch("builtins.__import__", side_effect=blocked_import):
        with pytest.raises(
            SemanticRuntimeDependencyError,
            match="not installed",
        ):
            resolve_semantic_runtime(
                {
                    SEMANTIC_PROVIDER_ENV: "ollama",
                    SEMANTIC_MODEL_ENV: "local-model",
                }
            )


def test_disabled_runtime_does_not_import_giadaware_ai() -> None:
    real_import = builtins.__import__
    attempted: list[str] = []

    def recording_import(
        name: str,
        globals: object = None,
        locals: object = None,
        fromlist: object = (),
        level: int = 0,
    ) -> ModuleType:
        if name == "giadaware_ai" or name.startswith("giadaware_ai."):
            attempted.append(name)
        return real_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    with patch("builtins.__import__", side_effect=recording_import):
        assert resolve_semantic_runtime({}) is None

    assert attempted == []
