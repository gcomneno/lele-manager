from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.application.assistant_context import (
    ResolvedAssistantContext,
)
from lele_manager.core.ask_vault import (
    AskVaultCitation,
    AskVaultResult,
)
from lele_manager.core.vault import write_lesson_markdown


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
        "search_lessons",
        lambda _body: [
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
        "search_lessons",
        lambda _body: [],
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
