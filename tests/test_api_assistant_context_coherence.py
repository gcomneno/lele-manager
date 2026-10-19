from __future__ import annotations

from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.composition import projection_store
from lele_manager.core.ask_vault import AskVaultCitation, AskVaultResult
from lele_manager.core.vault import write_lesson_markdown
from lele_manager.core.vault_registry import ActiveVaultContext


def _context(root: Path, label: str) -> ActiveVaultContext:
    return ActiveVaultContext(
        vault_id=label,
        display_name=label,
        vault_dir=root / label,
        projection_path=root / "data" / label / "lessons.jsonl",
        candidates_path=root / "data" / label / "candidates.json",
        topic_model_path=root / "cache" / label / "topic_model.joblib",
        duplicate_decision_scope=label,
    )


@pytest.mark.parametrize("endpoint", ["/assistant-context", "/ask-vault"])
@pytest.mark.parametrize("switch_at", ["capture", "after-search"])
@pytest.mark.parametrize("search_mode", ["browse", "lexical", "semantic"])
def test_assistant_search_and_canonical_reads_share_captured_vault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    switch_at: str,
    search_mode: str,
) -> None:
    first, second = _context(tmp_path, "A"), _context(tmp_path, "B")
    for context in (first, second):
        rows = []
        for lesson_id in ("topic/shared", f"topic/only-{context.vault_id}"):
            write_lesson_markdown(
                context.vault_dir,
                lesson_id=lesson_id,
                body=f"Canonical {context.vault_id}: {lesson_id}.",
                topic="topic",
                source="synthetic",
                importance=3,
                tags=[],
                date="2026-10-01",
            )
            rows.append({
                "id": lesson_id,
                "text": f"coherence projection {context.vault_id}",
                "topic": "topic",
                "importance": 3,
            })
        projection_store(context.projection_path).publish(rows)

    # A second global lookup would select B, including its colliding shared ID.
    active = first
    captures: list[ActiveVaultContext] = []

    def resolve_active() -> ActiveVaultContext:
        nonlocal active
        captured = active
        captures.append(captured)
        if switch_at == "capture":
            active = second
        return captured

    monkeypatch.setattr(server, "DATA_PATH", None)
    monkeypatch.setattr(server, "MODEL_PATH", None)
    monkeypatch.setattr(server, "get_active_vault_context", resolve_active)

    search_contexts: list[ActiveVaultContext] = []
    original_search = server._search_lessons

    def search(body, *, context):
        nonlocal active
        search_contexts.append(context)
        results = original_search(body, context=context)
        active = second
        return results

    monkeypatch.setattr(server, "_search_lessons", search)

    canonical_contexts: list[ActiveVaultContext] = []
    original_resolve = server.resolve_assistant_context_lesson_ids

    def resolve_canonical(*, lesson_ids, context):
        canonical_contexts.append(context)
        assert active is second
        return original_resolve(lesson_ids=lesson_ids, context=context)

    monkeypatch.setattr(
        server, "resolve_assistant_context_lesson_ids", resolve_canonical
    )

    loaded_models: list[str] = []
    if search_mode == "semantic":
        for context in (first, second):
            context.topic_model_path.parent.mkdir(parents=True)
            context.topic_model_path.write_bytes(b"synthetic model seam")
        monkeypatch.setattr(server.app.state, "sim_index_lock", Lock(), raising=False)
        monkeypatch.setattr(server.app.state, "sim_index", None, raising=False)
        monkeypatch.setattr(server.app.state, "sim_index_key", None, raising=False)
        pipeline = object()

        def load_model(path):
            loaded_models.append(path)
            return pipeline

        monkeypatch.setattr(server, "load_topic_model", load_model)
        monkeypatch.setattr(
            server.LessonSimilarityIndex,
            "from_topic_pipeline",
            lambda **kwargs: SimpleNamespace(transformer=pipeline),
        )
        monkeypatch.setattr(
            server,
            "similar_by_text",
            lambda df, *args, **kwargs: [
                SimpleNamespace(lesson_id=lesson_id, score=0.9)
                for lesson_id in df["id"]
            ],
        )

    observed_scopes = []

    def ask(*, question, context):
        observed_scopes.append(context)
        return AskVaultResult(
            outcome="answered",
            answer="Synthetic answer.",
            citations=(AskVaultCitation("topic/shared"),),
        )

    monkeypatch.setattr(
        server, "_ask_vault_service", lambda: SimpleNamespace(ask=ask)
    )
    query = {"browse": None, "lexical": "coherence", "semantic": "meaning"}[
        search_mode
    ]
    body = {"search": {"q": query, "limit": 20}}
    if endpoint == "/ask-vault":
        body["question"] = "What does this Vault say?"

    response = TestClient(server.app).post(endpoint, json=body)

    assert response.status_code == 200
    assert captures == [first]
    assert len(search_contexts) == len(canonical_contexts) == 1
    assert search_contexts[0] is canonical_contexts[0] is first
    expected_ids = ["topic/only-A", "topic/shared"]
    if endpoint == "/assistant-context":
        payload = response.json()
        assert payload["lesson_ids"] == expected_ids
        assert payload["n_lessons"] == 2
        for lesson_id in expected_ids:
            assert f"Canonical A: {lesson_id}." in payload["markdown"]
        assert "Canonical B:" not in payload["markdown"]
        assert "projection" not in payload["markdown"]
    else:
        assert response.json()["scope_lesson_ids"] == expected_ids
        assert len(observed_scopes) == 1
        assert [lesson.text for lesson in observed_scopes[0].lessons] == [
            f"Canonical A: {lesson_id}." for lesson_id in expected_ids
        ]

    if search_mode == "semantic":
        assert loaded_models == [str(first.topic_model_path)]
        assert server.app.state.sim_index_key == server._similarity_cache_key(
            first.projection_path, first.topic_model_path, first
        )
