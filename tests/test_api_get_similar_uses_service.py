from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient


def test_get_similar_uses_similarity_service(monkeypatch) -> None:
    from lele_manager.api import server

    df = pd.DataFrame(
        [
            {"id": "1", "text": "hello world"},
            {"id": "2", "text": "hello there"},
        ]
    )

    monkeypatch.setattr(server, "load_lessons_df", lambda: df)
    monkeypatch.setattr(server, "build_similarity_index", lambda _df: SimpleNamespace(transformer=None))

    calls = {}

    def _fake_similar_by_lesson_id(*, df, lesson_id, transformer, top_k, min_score, ranking=None):
        calls["lesson_id"] = lesson_id
        calls["top_k"] = top_k
        calls["min_score"] = min_score
        return [SimpleNamespace(lesson_id="2", score=0.9)]

    monkeypatch.setattr(server, "similar_by_lesson_id", _fake_similar_by_lesson_id)

    client = TestClient(server.app)
    resp = client.get("/lessons/1/similar", params={"top_k": 7, "min_score": 0.25})
    assert resp.status_code == 200

    assert calls["lesson_id"] == "1"
    assert calls["top_k"] == 7
    assert calls["min_score"] == 0.25

    body = resp.json()
    assert body["query"] == "hello world"
    assert len(body["results"]) == 1
    assert body["results"][0]["id"] == "2"
