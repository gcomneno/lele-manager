from __future__ import annotations

from pathlib import Path

import lele_manager.api.server as server_mod
import pandas as pd
from fastapi.testclient import TestClient

from lele_manager.api.server import app


def _train_fixture(monkeypatch, tmp_path: Path) -> TestClient:
    data_path = tmp_path / "lessons.jsonl"
    model_path = tmp_path / "topic_model.joblib"
    data_path.write_text(
        "\n".join(
            [
                '{"id":"python/a","text":"python pandas pytest tips","topic":"python","tags":["python","pytest"]}',
                '{"id":"python/b","text":"python sklearn pytest models","topic":"python","tags":["python","pytest","ml"]}',
                '{"id":"linux/c","text":"linux kernel networking","topic":"linux","tags":["linux"]}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_mod, "DATA_PATH", data_path)
    monkeypatch.setattr(server_mod, "MODEL_PATH", model_path)
    client = TestClient(app)
    r_train = client.post("/train/topic")
    assert r_train.status_code == 200, r_train.text
    return client


def test_similar_explain_false_omits_debug_fields(monkeypatch, tmp_path) -> None:
    client = _train_fixture(monkeypatch, tmp_path)
    r = client.post("/similar", json={"text": "python pytest", "top_k": 3, "min_score": 0.0})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload.get("meta") is None
    for item in payload["results"]:
        assert "rank" not in item or item.get("rank") is None
        assert "topic" not in item or item.get("topic") is None


def test_similar_explain_true_includes_rank_topic_meta(monkeypatch, tmp_path) -> None:
    client = _train_fixture(monkeypatch, tmp_path)
    r = client.post(
        "/similar",
        params={"explain": "true"},
        json={"text": "python pytest", "top_k": 3, "min_score": 0.0},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    meta = payload["meta"]
    assert meta["top_k"] == 3
    assert meta["min_score"] == 0.0
    assert isinstance(meta["data_mtime_ns"], int)
    assert isinstance(meta["model_mtime_ns"], int)
    assert payload["results"]
    first = payload["results"][0]
    assert first["rank"] == 1
    assert first["topic"] in {"python", "linux"}


def test_get_similar_by_id_explain_tag_overlap(monkeypatch, tmp_path) -> None:
    client = _train_fixture(monkeypatch, tmp_path)
    r = client.get("/lessons/python/a/similar", params={"top_k": 5, "min_score": 0.0, "explain": True})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["meta"]["query_topic"] == "python"
    assert "pytest" in (payload["meta"].get("query_tags") or [])
    shared_hits = [item for item in payload["results"] if item.get("tags_shared")]
    assert shared_hits, "expected at least one result with shared tags"
    assert "pytest" in shared_hits[0]["tags_shared"]


def test_editor_suggest_explain_matches_similar(monkeypatch, tmp_path) -> None:
    client = _train_fixture(monkeypatch, tmp_path)
    fm_text = (
        "---\n"
        "topic: python\n"
        "tags: [python, pytest]\n"
        "---\n\n"
        "python pytest workflow"
    )
    payload = {"text": fm_text, "top_k": 3, "min_score": 0.0}
    r1 = client.post("/similar", params={"explain": "true"}, json=payload)
    r2 = client.post("/editor/suggest", params={"explain": "true"}, json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json() == r1.json()
    assert r1.json()["meta"].get("query_tags") == ["pytest", "python"]


def test_parse_frontmatter_tags_helper() -> None:
    from lele_manager.api.server import _parse_frontmatter_tags

    text = "---\ntopic: t\ntags: [a, b]\n---\n\nbody"
    assert _parse_frontmatter_tags(text) == {"a", "b"}
