from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient


def test_post_similar_batch_preserves_order(monkeypatch) -> None:
    from lele_manager.api import server

    # Dataset minimo in memoria
    df = pd.DataFrame(
        [
            {"id": "1", "text": "hello world"},
            {"id": "2", "text": "hello there"},
        ]
    )

    monkeypatch.setattr(server, "load_lessons_df", lambda: df)
    monkeypatch.setattr(server, "build_similarity_index", lambda _df: SimpleNamespace(transformer="X"))

    # Finto service: ritorna un risultato deterministico per ogni query
    def _fake_similar_by_text(df, query_text, transformer, top_k, min_score, ranking=None):
        assert transformer == "X"
        return [SimpleNamespace(lesson_id="2", score=0.9)]

    monkeypatch.setattr(server, "similar_by_text", _fake_similar_by_text)

    client = TestClient(server.app)

    payload = {
        "items": [
            {"text": "hello", "top_k": 5, "min_score": 0.0},
            {"text": "world", "top_k": 5, "min_score": 0.0},
        ]
    }

    r = client.post("/similar/batch", json=payload)
    assert r.status_code == 200
    j = r.json()
    assert list(j.keys()) == ["items"]
    assert len(j["items"]) == 2
    assert j["items"][0]["query"] == "hello"
    assert j["items"][1]["query"] == "world"
    assert j["items"][0]["results"][0]["id"] == "2"
