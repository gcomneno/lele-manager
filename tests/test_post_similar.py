from __future__ import annotations

from fastapi.testclient import TestClient
from lele_manager.api.server import app
from pathlib import Path
import pandas as pd


client = TestClient(app)


def test_post_similar_empty_text():
    r = client.post("/similar", json={"text": "   "})
    assert r.status_code == 400


def test_post_similar_model_missing(monkeypatch):
    from lele_manager.api import server

    # dataset non vuoto, altrimenti /similar risponde 400 prima del check modello
    monkeypatch.setattr(
        server,
        "load_lessons_df",
        lambda: pd.DataFrame([{"id": "1", "text": "hello", "topic": "t"}]),
    )

    # forza modello mancante
    monkeypatch.setattr(server, "get_model_path", lambda: Path("/nonexistent/topic_model.joblib"))

    r = client.post("/similar", json={"text": "hello", "top_k": 5, "min_score": 0.1})
    assert r.status_code == 503
