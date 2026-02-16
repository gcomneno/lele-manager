from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from lele_manager.api.server import app


def test_similar_warm_is_faster_than_cold(monkeypatch, tmp_path: Path):
    from lele_manager.api import server

    client = TestClient(app)

    # Ensure non-empty dataset
    monkeypatch.setattr(
        server,
        "load_lessons_df",
        lambda: pd.DataFrame(
            [
                {"id": "1", "text": "hello world", "topic": "t"},
                {"id": "2", "text": "hello there", "topic": "t"},
                {"id": "3", "text": "goodbye", "topic": "t"},
            ]
        ),
    )

    # Ensure model exists
    model_path = tmp_path / "topic_model.joblib"
    model_path.write_bytes(b"dummy")
    monkeypatch.setattr(server, "get_model_path", lambda: model_path)

    # Avoid real pipeline I/O
    monkeypatch.setattr(server, "load_topic_model", lambda *_a, **_kw: object())

    # Reset cache for deterministic cold/warm behavior
    server.invalidate_similarity_cache()

    calls = {"n": 0}

    import numpy as np

    class _DummyTransformer:
        def transform(self, df):
            return np.zeros((len(df), 1), dtype=float)

    class _DummyIndex:
        # Needed by similarity_service wiring
        transformer = _DummyTransformer()

        def most_similar(self, query_text: str, top_k: int, min_score: float):
            return []

    def _from_topic_pipeline(*_args, **_kw):
        calls["n"] += 1
        # simulate "costly" build (cold path only)
        time.sleep(0.06)
        return _DummyIndex()

    monkeypatch.setattr(server.LessonSimilarityIndex, "from_topic_pipeline", staticmethod(_from_topic_pipeline))

    # cold
    t0 = time.perf_counter()
    r1 = client.post("/similar", json={"text": "hello", "top_k": 5, "min_score": 0.0})
    t1 = time.perf_counter()

    assert r1.status_code == 200

    # warm
    t2 = time.perf_counter()
    r2 = client.post("/similar", json={"text": "hello", "top_k": 5, "min_score": 0.0})
    t3 = time.perf_counter()

    assert r2.status_code == 200

    cold = t1 - t0
    warm = t3 - t2

    # The second call should be significantly faster (no sleep)
    assert warm < cold
    assert calls["n"] == 1
