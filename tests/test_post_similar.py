from __future__ import annotations

from fastapi.testclient import TestClient
from lele_manager.api.server import app
from pathlib import Path

import lele_manager.api.server as server_mod

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


def test_post_similar_smoke_uses_trained_model(monkeypatch, tmp_path):
    # --- Arrange: dataset + model temp ---
    data_path = tmp_path / "lessons.jsonl"
    model_path = tmp_path / "topic_model.joblib"

    # Minimal JSONL con topic per poter trainare il model
    data_path.write_text(
        "\n".join(
            [
                '{"id":"1","text":"python pandas commonterm","topic":"python","importance":1}',
                '{"id":"2","text":"python sklearn commonterm","topic":"python","importance":1}',
                '{"id":"3","text":"python linux commonterm","topic":"linux","importance":1}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Override paths usati dal server
    monkeypatch.setattr(server_mod, "DATA_PATH", data_path)
    monkeypatch.setattr(server_mod, "MODEL_PATH", model_path)

    client = TestClient(app)

    # Train modello (endpoint già presente)
    r_train = client.post("/train/topic")
    assert r_train.status_code == 200, r_train.text

    # --- Act ---
    r = client.post("/similar", json={"text": "python pandas", "top_k": 3, "min_score": 0.0})

    # --- Assert ---
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["query"] == "python pandas"
    assert isinstance(payload["results"], list)
    assert 1 <= len(payload["results"]) <= 3

    for item in payload["results"]:
        assert isinstance(item["id"], str)
        assert isinstance(item["score"], float)
        assert isinstance(item["text_preview"], str)
