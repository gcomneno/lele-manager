"""Real optional API with fake provider construction and bounded inference."""

import builtins
import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from giadaware_ai import (
    AIConfigurationError,
    AIError,
    AIInvalidResponseError,
    AITimeoutError,
    AIUnavailableError,
    AIUnsupportedCapabilityError,
    backends,
)

from lele_manager.api import server
from lele_manager.core.vault import write_lesson_markdown


@pytest.fixture(autouse=True)
def isolated_provider_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("LELE_VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    for name in (
        "LELE_ASK_VAULT_PROVIDER",
        "LELE_ASK_VAULT_MODEL",
        "LELE_ASK_VAULT_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(backends, "OllamaBackend", Mock(side_effect=AssertionError))


def _write_lesson(
    vault,
    lesson_id: str,
    *,
    body: str,
    lifecycle: str = "active",
) -> None:
    write_lesson_markdown(
        vault,
        lesson_id=lesson_id,
        body=body,
        topic=lesson_id.split("/", 1)[0],
        source="private-test-source",
        importance=3,
        tags=["ask", "vault"],
        date="2026-09-28",
        title=f"Title {lesson_id}",
        lifecycle=lifecycle,
    )



@pytest.mark.parametrize(
    "result,status,code",
    [
        (
            {
                "outcome": "answered",
                "answer": "Grounded.",
                "citation_lesson_ids": ["topic/current"],
            },
            200,
            None,
        ),
        (
            {
                "outcome": "insufficient-support",
                "answer": "Insufficient knowledge.",
                "citation_lesson_ids": [],
            },
            200,
            None,
        ),
        (
            {
                "outcome": "answered",
                "answer": "Invented.",
                "citation_lesson_ids": ["topic/outside"],
            },
            502,
            "ask_vault_invalid_result",
        ),
        (
            {
                "outcome": "answered",
                "answer": "No citations.",
                "citation_lesson_ids": [],
            },
            502,
            "ask_vault_invalid_result",
        ),
        (AIInvalidResponseError("PRIVATE_CREDENTIAL"), 502, "ask_vault_invalid_result"),
        (
            AIConfigurationError("PRIVATE_CREDENTIAL"),
            503,
            "ask_vault_provider_unavailable",
        ),
        (
            AIUnavailableError("PRIVATE_CREDENTIAL"),
            503,
            "ask_vault_provider_unavailable",
        ),
        (
            AIUnsupportedCapabilityError("PRIVATE_CREDENTIAL"),
            503,
            "ask_vault_provider_unavailable",
        ),
        (AIError("PRIVATE_CREDENTIAL"), 503, "ask_vault_provider_unavailable"),
        (AITimeoutError("PRIVATE_CREDENTIAL"), 504, "ask_vault_provider_timeout"),
    ],
)
def test_enabled_composition_through_api_uses_one_bounded_inference(
    tmp_path,
    monkeypatch,
    result,
    status,
    code,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_ASK_VAULT_PROVIDER", "ollama")
    monkeypatch.setenv("LELE_ASK_VAULT_MODEL", "synthetic-model")
    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "topic/current",
        body="Canonical synthetic knowledge.",
        lifecycle="review-needed",
    )
    backend = Mock()
    if isinstance(result, Exception):
        backend.generate_json.side_effect = result
    else:
        backend.generate_json.return_value = result
    constructor = Mock(return_value=backend)
    monkeypatch.setattr(backends, "OllamaBackend", constructor)
    response = TestClient(server.app).post(
        "/ask-vault",
        json={"question": " \t" + "🐒" * 4000 + "\n ", "lesson_ids": ["topic/current"]},
    )
    assert response.status_code == status
    assert "PRIVATE_CREDENTIAL" not in response.text
    constructor.assert_called_once_with(
        model="synthetic-model",
        base_url="http://127.0.0.1:11434",
        timeout=120.0,
    )
    backend.generate_json.assert_called_once()
    sent = json.loads(backend.generate_json.call_args.kwargs["user_prompt"])
    assert sent["question"] == "🐒" * 4000
    assert sent["lessons"][0]["text"] == "Canonical synthetic knowledge."
    if code is not None:
        assert response.json()["detail"]["code"] == code
    else:
        payload = response.json()
        assert payload["scope_lesson_ids"] == ["topic/current"]
        assert payload["generated_synthesis"] is True
        if payload["outcome"] == "answered":
            assert payload["citations"] == [
                {
                    "lesson_id": "topic/current",
                    "title": "Title topic/current",
                    "lifecycle": "review-needed",
                    "superseded_by": None,
                }
            ]
        else:
            assert payload["citations"] == []



@pytest.mark.parametrize(
    "module",
    ["giadaware_ai.backends", "lele_manager.adapters.giadaware_ai_ask_vault"],
)
def test_enabled_dependency_import_failure_is_a_redacted_503(
    tmp_path,
    monkeypatch,
    module,
) -> None:
    monkeypatch.setenv("LELE_ASK_VAULT_PROVIDER", "ollama")
    monkeypatch.setenv("LELE_ASK_VAULT_MODEL", "synthetic-model")
    context = server.get_active_vault_context()
    _write_lesson(context.vault_dir, "topic/current", body="Synthetic knowledge.")
    original_import = builtins.__import__
    attempts = []

    def failing_import(name, *args, **kwargs):
        if name == module:
            attempts.append(name)
            raise ImportError("PRIVATE_CREDENTIAL")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    response = TestClient(server.app).post(
        "/ask-vault",
        json={"question": "?", "lesson_ids": ["topic/current"]},
    )
    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "ask_vault_provider_unavailable",
            "message": "Ask-this-Vault synthesis provider is unavailable.",
        }
    }
    assert attempts == [module]
    backends.OllamaBackend.assert_not_called()
