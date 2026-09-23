from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.core.context_pack_store import (
    ContextPackStore,
    context_pack_store_path,
)
from lele_manager.core.vault import write_lesson_markdown


def _write_lesson(
    vault: Path,
    lesson_id: str,
    *,
    body: str,
    lifecycle: str = "active",
    relationships: dict[str, list[str]] | None = None,
) -> None:
    topic = lesson_id.split("/", 1)[0]
    write_lesson_markdown(
        vault,
        lesson_id=lesson_id,
        body=body,
        topic=topic,
        source="private-test-source",
        importance=3,
        tags=["assistant", "context"],
        date="2026-09-23",
        title=f"Title {lesson_id}",
        lifecycle=lifecycle,
        relationships=relationships or {},
    )


def test_assistant_context_lesson_ids_preserve_explicit_order_and_use_canonical(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        "python/alpha",
        body="Canonical alpha.",
    )
    _write_lesson(
        context.vault_dir,
        "python/bravo",
        body="Canonical bravo.",
        lifecycle="review-needed",
    )

    client = TestClient(server.app)
    response = client.post(
        "/assistant-context",
        json={
            "lesson_ids": [
                "python/bravo",
                "python/alpha",
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["lesson_ids"] == [
        "python/bravo",
        "python/alpha",
    ]
    assert payload["n_lessons"] == 2
    assert payload["markdown"].index("Canonical bravo.") < payload[
        "markdown"
    ].index("Canonical alpha.")
    assert "Lifecycle: `review-needed`" in payload["markdown"]
    assert "_Generated:" not in payload["markdown"]
    assert "private-test-source" not in payload["markdown"]


def test_assistant_context_search_uses_search_only_for_identity_and_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        "python/current",
        body="CURRENT CANONICAL BODY",
    )

    def fake_search(_body):
        return [
            SimpleNamespace(
                id="python/current",
                text="STALE PROJECTION BODY",
                rank=1,
                hybrid_score=999,
            )
        ]

    monkeypatch.setattr(server, "search_lessons", fake_search)

    client = TestClient(server.app)
    response = client.post(
        "/assistant-context",
        json={
            "search": {
                "q": "current",
                "limit": 20,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["lesson_ids"] == ["python/current"]
    assert "CURRENT CANONICAL BODY" in payload["markdown"]
    assert "STALE PROJECTION BODY" not in payload["markdown"]
    assert "hybrid_score" not in payload["markdown"]
    assert "999" not in payload["markdown"]


def test_assistant_context_pack_preserves_pack_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        "python/bravo",
        body="Bravo pack body.",
    )
    _write_lesson(
        context.vault_dir,
        "python/alpha",
        body="Alpha pack body.",
    )

    store = ContextPackStore(context_pack_store_path())
    pack = store.create(
        name="Assistant task",
        vault_id=context.vault_id,
        lesson_ids=(
            "python/bravo",
            "python/alpha",
        ),
    )

    client = TestClient(server.app)
    response = client.post(
        "/assistant-context",
        json={"context_pack_id": pack.id},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["lesson_ids"] == [
        "python/bravo",
        "python/alpha",
    ]
    assert payload["markdown"].index("Bravo pack body.") < payload[
        "markdown"
    ].index("Alpha pack body.")


def test_assistant_context_pack_rejects_broken_references(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        "python/current",
        body="Current body.",
    )

    store = ContextPackStore(context_pack_store_path())
    pack = store.create(
        name="Broken pack",
        vault_id=context.vault_id,
        lesson_ids=(
            "python/current",
            "python/missing",
        ),
    )

    client = TestClient(server.app)
    response = client.post(
        "/assistant-context",
        json={"context_pack_id": pack.id},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "assistant_context_has_broken_references"
    assert detail["lesson_ids"] == ["python/missing"]


def test_assistant_context_requires_exactly_one_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(server.app)

    empty = client.post(
        "/assistant-context",
        json={},
    )
    assert empty.status_code == 422
    assert empty.json()["detail"]["code"] == "assistant_context_scope_invalid"

    conflicting = client.post(
        "/assistant-context",
        json={
            "lesson_ids": ["python/a"],
            "context_pack_id": "pack-id",
        },
    )
    assert conflicting.status_code == 422
    assert conflicting.json()["detail"]["code"] == "assistant_context_scope_invalid"


def test_assistant_context_direct_scope_rejects_missing_canonical_lesson(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(server.app)

    response = client.post(
        "/assistant-context",
        json={"lesson_ids": ["python/missing"]},
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]["code"]
        == "assistant_context_lesson_not_found"
    )
