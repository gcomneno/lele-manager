import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.core.vault_registry import ActiveVaultContext


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class _DummyTransformer:
    def transform(self, df):
        # minimal feature matrix: (n_rows, 1)
        return np.zeros((len(df), 1), dtype=float)


class _DummyIndex:
    transformer = _DummyTransformer()

    def most_similar(self, query_text: str, top_k: int, min_score: float):
        return []


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_path = tmp_path / "lessons.jsonl"
    model_path = tmp_path / "topic_model.joblib"
    model_path.write_bytes(b"dummy")  # must exist for build_similarity_index

    _write_jsonl(
        data_path,
        [
            {
                "id": "1",
                "text": "hello",
                "topic": "t1",
                "source": None,
                "importance": 1,
                "tags": None,
                "date": "2025-01-01",
                "title": None,
            },
            {
                "id": "2",
                "text": "world",
                "topic": "t1",
                "source": None,
                "importance": 2,
                "tags": None,
                "date": "2026-01-01",
                "title": None,
            },
        ],
    )

    # Point server to temp paths
    context = ActiveVaultContext(
        "test-vault", "Test vault", tmp_path, data_path,
        tmp_path / "candidates.json", model_path, "test-vault",
    )
    dependency = server.get_active_vault_context
    server.app.dependency_overrides[dependency] = lambda: context
    monkeypatch.setattr(server, "get_active_vault_context", lambda: context)

    # Avoid real joblib pipeline I/O
    monkeypatch.setattr(server, "load_topic_model", lambda *_args, **_kw: object())

    # Reset cache between tests
    server.invalidate_similarity_cache()

    try:
        yield TestClient(server.app), model_path
    finally:
        server.app.dependency_overrides.pop(dependency, None)


def test_similarity_index_is_cached_across_requests(client, monkeypatch: pytest.MonkeyPatch):
    c, _model_path = client

    calls = {"n": 0}

    def _from_topic_pipeline(*_args, **_kw):
        calls["n"] += 1
        return _DummyIndex()

    monkeypatch.setattr(server.LessonSimilarityIndex, "from_topic_pipeline", staticmethod(_from_topic_pipeline))

    r1 = c.post("/similar", json={"text": "x", "top_k": 3, "min_score": 0.0})
    assert r1.status_code == 200

    r2 = c.post("/similar", json={"text": "y", "top_k": 3, "min_score": 0.0})
    assert r2.status_code == 200

    assert calls["n"] == 1


def test_similarity_cache_invalidated_after_train_topic(client, monkeypatch: pytest.MonkeyPatch):
    c, model_path = client

    calls = {"n": 0}

    def _from_topic_pipeline(*_args, **_kw):
        calls["n"] += 1
        return _DummyIndex()

    monkeypatch.setattr(server.LessonSimilarityIndex, "from_topic_pipeline", staticmethod(_from_topic_pipeline))

    # First call builds index
    r1 = c.post("/similar", json={"text": "x", "top_k": 3, "min_score": 0.0})
    assert r1.status_code == 200
    assert calls["n"] == 1

    # Stub training to be cheap + ensure model file mtime changes
    monkeypatch.setattr(server, "train_topic_model", lambda _df: object())

    def _save_topic_model(_pipeline, path: str | None):
        assert path is not None
        p = Path(path)
        p.write_bytes(p.read_bytes() + b".")  # bump mtime deterministically

    monkeypatch.setattr(server, "save_topic_model", _save_topic_model)

    rt = c.post("/train/topic")
    assert rt.status_code == 200

    # Next call must rebuild (invalidate + mtime bump)
    r2 = c.post("/similar", json={"text": "y", "top_k": 3, "min_score": 0.0})
    assert r2.status_code == 200
    assert calls["n"] == 2


def test_similarity_request_keeps_projection_model_and_cache_key_in_one_context(
    client, monkeypatch: pytest.MonkeyPatch
):
    c, _model_path = client
    context = server.get_active_vault_context()
    frame = pd.DataFrame([{"id": "1", "text": "one"}])
    seen: list[object] = []
    monkeypatch.setattr(server, "load_lessons_df", lambda supplied: seen.append(supplied) or frame)
    monkeypatch.setattr(server, "build_similarity_index", lambda _df, supplied: seen.append(supplied) or _DummyIndex())
    response = c.post("/similar", json={"text": "one"})
    assert response.status_code == 200
    assert seen == [context, context]
    key = server._similarity_cache_key(
        context.projection_path, context.topic_model_path, context
    )
    assert key[:3] == (context.vault_id, str(context.projection_path), str(context.topic_model_path))
