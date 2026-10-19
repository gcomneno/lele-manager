from __future__ import annotations

from dataclasses import dataclass
import builtins
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.application.ask_vault import (
    AskVaultGroundingError,
    AskVaultProviderTimeoutError,
    AskVaultProviderUnavailableError,
)
from lele_manager.application.assistant_context import (
    ResolvedAssistantContext,
)
from lele_manager.core.ask_vault import (
    AskVaultCitation,
    AskVaultResult,
)
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
    original_import = builtins.__import__
    attempted = []

    def guarded_import(name, *args, **kwargs):
        if name.startswith("giadaware_ai") or name.endswith("giadaware_ai_ask_vault"):
            attempted.append(name)
            raise AssertionError("Core API must not import optional AI")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    yield
    # Zero optional imports also proves zero provider construction.
    assert attempted == []


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


@dataclass
class StubAskService:
    result: AskVaultResult
    observed_context: ResolvedAssistantContext | None = None

    def ask(
        self,
        *,
        question: str,
        context: ResolvedAssistantContext,
    ) -> AskVaultResult:
        assert question
        self.observed_context = context
        return self.result


def test_ask_vault_reuses_exactly_one_scope_contract(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(server.app)

    response = client.post(
        "/ask-vault",
        json={"question": "What does the Vault say?"},
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "assistant_context_scope_invalid"
    )


def test_ask_vault_exposes_grounded_canonical_citations(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        "python/current",
        body="Canonical maintained answer.",
        lifecycle="review-needed",
    )

    stub = StubAskService(
        result=AskVaultResult(
            outcome="answered",
            answer="The maintained answer is available.",
            citations=(AskVaultCitation("python/current"),),
        )
    )
    monkeypatch.setattr(
        server,
        "_ask_vault_service",
        lambda: stub,
    )

    client = TestClient(server.app)
    response = client.post(
        "/ask-vault",
        json={
            "question": "What is maintained?",
            "lesson_ids": ["python/current"],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload == {
        "outcome": "answered",
        "answer": "The maintained answer is available.",
        "generated_synthesis": True,
        "citations": [
            {
                "lesson_id": "python/current",
                "title": "Title python/current",
                "lifecycle": "review-needed",
                "superseded_by": None,
            }
        ],
        "scope_lesson_ids": ["python/current"],
    }

    assert stub.observed_context is not None
    assert stub.observed_context.lesson_ids == ("python/current",)
    assert (
        stub.observed_context.lessons[0].text
        == "Canonical maintained answer."
    )


def test_ask_vault_search_uses_projection_only_for_identity_and_order(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        "python/current",
        body="CURRENT CANONICAL BODY",
    )

    monkeypatch.setattr(
        server,
        "_search_lessons",
        lambda _body, *, context: [
            SimpleNamespace(
                id="python/current",
                text="STALE PROJECTION BODY",
                rank=1,
                hybrid_score=999,
            )
        ],
    )

    stub = StubAskService(
        result=AskVaultResult(
            outcome="answered",
            answer="Grounded.",
            citations=(AskVaultCitation("python/current"),),
        )
    )
    monkeypatch.setattr(
        server,
        "_ask_vault_service",
        lambda: stub,
    )

    client = TestClient(server.app)
    response = client.post(
        "/ask-vault",
        json={
            "question": "What is current?",
            "search": {
                "q": "current",
                "limit": 20,
            },
        },
    )

    assert response.status_code == 200
    assert stub.observed_context is not None
    assert (
        stub.observed_context.lessons[0].text
        == "CURRENT CANONICAL BODY"
    )
    assert "STALE PROJECTION BODY" not in (
        stub.observed_context.lessons[0].text
    )


def test_empty_search_returns_insufficient_support_without_provider(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    monkeypatch.setattr(
        server,
        "_search_lessons",
        lambda _body, *, context: [],
    )

    client = TestClient(server.app)
    response = client.post(
        "/ask-vault",
        json={
            "question": "Unknown detail?",
            "search": {
                "q": "nothing",
                "limit": 20,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["outcome"] == "insufficient-support"
    assert payload["citations"] == []
    assert payload["scope_lesson_ids"] == []


@pytest.mark.parametrize(
    "question", ["", " \t\n", "x" * 4001, "\ud800", "\udfff", "x\ud800 "]
)
@pytest.mark.parametrize("scope", [{}, {"lesson_ids": ["topic/missing"]}])
def test_question_validation_precedes_scope_and_composition(
    monkeypatch,
    question,
    scope,
) -> None:
    resolve = Mock(side_effect=AssertionError("Scope must not be resolved"))
    compose = Mock(side_effect=AssertionError("Provider must not be composed"))
    monkeypatch.setattr(server, "_resolve_assistant_context_scope", resolve)
    monkeypatch.setattr(server, "_ask_vault_service", compose)
    response = TestClient(server.app).post(
        "/ask-vault",
        content=json.dumps({"question": question, **scope}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "ask_vault_question_invalid",
            "message": "Ask-this-Vault question is invalid.",
        }
    }
    resolve.assert_not_called()
    compose.assert_not_called()


@pytest.mark.parametrize("provider", [None, "ollama", "PRIVATE_INVALID_PROVIDER"])
def test_empty_scope_never_composes_or_imports_optional_dependencies(
    tmp_path,
    monkeypatch,
    provider,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    if provider is not None:
        monkeypatch.setenv("LELE_ASK_VAULT_PROVIDER", provider)
    monkeypatch.setenv("LELE_ASK_VAULT_MODEL", "synthetic-model")
    monkeypatch.setattr(server, "_search_lessons", lambda _body, *, context: [])
    compose = Mock(side_effect=AssertionError("Empty scope must not compose"))
    monkeypatch.setattr(server, "_ask_vault_service", compose)
    original_import = builtins.__import__
    optional_imports = []

    def guarded_import(name, *args, **kwargs):
        if name.startswith("giadaware_ai") or name.endswith("giadaware_ai_ask_vault"):
            optional_imports.append(name)
            raise AssertionError("Optional import is forbidden")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    response = TestClient(server.app).post(
        "/ask-vault",
        json={"question": "?", "search": {"q": "nothing"}},
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "insufficient-support"
    assert response.json()["scope_lesson_ids"] == []
    assert response.json()["citations"] == []
    compose.assert_not_called()
    assert optional_imports == []


@pytest.mark.parametrize(
    "scope,status", [({}, 422), ({"lesson_ids": ["topic/missing"]}, 404)]
)
def test_scope_resolution_failure_precedes_composition(
    tmp_path, monkeypatch, scope, status
):
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    compose = Mock(side_effect=AssertionError("Invalid scope must not compose"))
    monkeypatch.setattr(server, "_ask_vault_service", compose)
    response = TestClient(server.app).post(
        "/ask-vault", json={"question": "?", **scope}
    )
    assert response.status_code == status
    compose.assert_not_called()


@pytest.mark.parametrize("stage", ["composition", "inference"])
@pytest.mark.parametrize(
    "error,status,code,message",
    [
        (
            AskVaultGroundingError,
            502,
            "ask_vault_invalid_result",
            "Ask-this-Vault synthesis response is invalid.",
        ),
        (
            AskVaultProviderUnavailableError,
            503,
            "ask_vault_provider_unavailable",
            "Ask-this-Vault synthesis provider is unavailable.",
        ),
        (
            AskVaultProviderTimeoutError,
            504,
            "ask_vault_provider_timeout",
            "Ask-this-Vault synthesis provider timed out.",
        ),
    ],
)
def test_typed_api_errors_use_fixed_redacted_details(
    tmp_path,
    monkeypatch,
    stage,
    error,
    status,
    code,
    message,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()
    _write_lesson(context.vault_dir, "topic/current", body="Synthetic knowledge.")
    service = Mock()
    compose = Mock(return_value=service)
    failure = compose if stage == "composition" else service.ask
    failure.side_effect = error("PRIVATE_CREDENTIAL")
    monkeypatch.setattr(server, "_ask_vault_service", compose)
    response = TestClient(server.app).post(
        "/ask-vault",
        json={"question": "?", "lesson_ids": ["topic/current"]},
    )
    assert response.status_code == status
    assert response.json() == {"detail": {"code": code, "message": message}}
    compose.assert_called_once_with()
    assert service.ask.call_count == (0 if stage == "composition" else 1)


@pytest.mark.parametrize("provider", [None, "PRIVATE_INVALID_PROVIDER", "ollama"])
def test_invalid_or_disabled_configuration_is_a_redacted_503(
    tmp_path,
    monkeypatch,
    provider,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    if provider is not None:
        monkeypatch.setenv("LELE_ASK_VAULT_PROVIDER", provider)
    context = server.get_active_vault_context()
    _write_lesson(context.vault_dir, "topic/current", body="Synthetic knowledge.")
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


def test_non_empty_scope_fails_closed_when_provider_is_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        "python/current",
        body="Canonical body.",
    )

    client = TestClient(server.app)
    response = client.post(
        "/ask-vault",
        json={
            "question": "What does it say?",
            "lesson_ids": ["python/current"],
        },
    )

    assert response.status_code == 503
    assert (
        response.json()["detail"]["code"]
        == "ask_vault_provider_unavailable"
    )
