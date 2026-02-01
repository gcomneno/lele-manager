from pathlib import Path
import json
from typing import List, Dict, Any

from fastapi.testclient import TestClient

from lele_manager.api import server


def _write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """Utility: scrive una lista di dict in formato JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_search_lessons_by_q(tmp_path, monkeypatch) -> None:
    """Ricerca con solo filtro testuale `q`."""
    data_path = tmp_path / "data" / "lessons.jsonl"

    records = [
        {
            "id": "1",
            "text": "LeLe su pytest e Python",
            "topic": "python",
            "source": "chatgpt",
            "importance": 4,
            "tags": ["python", "pytest"],
            "date": "2025-01-01",
            "title": "Pytest basics",
        },
        {
            "id": "2",
            "text": "LeLe su Git e branching",
            "topic": "git",
            "source": "note",
            "importance": 3,
            "tags": ["git"],
            "date": "2025-01-02",
            "title": "Git branching",
        },
        {
            "id": "3",
            "text": "Altra lesson generica",
            "topic": "misc",
            "source": "note",
            "importance": 2,
            "tags": ["varie"],
            "date": "2025-01-03",
            "title": "Misc",
        },
    ]
    _write_jsonl(data_path, records)

    # Puntiamo il server al JSONL temporaneo
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)

    client = TestClient(server.app)

    resp = client.post(
        "/lessons/search",
        json={
            "q": "pytest",
            "limit": 10,
        },
    )
    assert resp.status_code == 200

    results = resp.json()
    assert isinstance(results, list)
    # Ci aspettiamo un solo match: la LeLe con id "1"
    assert len(results) == 1

    lele = results[0]
    assert lele["id"] == "1"
    assert "pytest" in lele["text"]
    # Controllo minimale su qualche campo di contorno
    assert lele["topic"] == "python"
    assert lele["source"] == "chatgpt"
    assert lele["importance"] == 4
    assert lele["tags"] == ["python", "pytest"]


def test_search_lessons_with_topic_source_and_importance(tmp_path, monkeypatch) -> None:
    """Ricerca con filtri combinati: topic_in + source_in + importance range."""
    data_path = tmp_path / "data" / "lessons.jsonl"

    records = [
        {
            "id": "1",
            "text": "LeLe Python molto importante",
            "topic": "python",
            "source": "note",
            "importance": 5,
            "tags": ["python"],
            "date": "2025-01-01",
            "title": "Python high importance",
        },
        {
            "id": "2",
            "text": "LeLe Python poco importante",
            "topic": "python",
            "source": "chatgpt",
            "importance": 2,
            "tags": ["python"],
            "date": "2025-01-02",
            "title": "Python low importance",
        },
        {
            "id": "3",
            "text": "LeLe Git media importanza",
            "topic": "git",
            "source": "note",
            "importance": 3,
            "tags": ["git"],
            "date": "2025-01-03",
            "title": "Git medium importance",
        },
        {
            "id": "4",
            "text": "Altra LeLe Python media importanza",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["python"],
            "date": "2025-01-04",
            "title": "Python medium importance",
        },
    ]
    _write_jsonl(data_path, records)

    # Puntiamo il server al JSONL temporaneo
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)

    client = TestClient(server.app)

    resp = client.post(
        "/lessons/search",
        json={
            "topic_in": ["python"],
            "source_in": ["note"],
            "importance_gte": 3,
            "importance_lte": 5,
            "limit": 10,
        },
    )
    assert resp.status_code == 200

    results = resp.json()
    assert isinstance(results, list)

    # Dovrebbero passare:
    # - id=1 (python, note, importance=5)
    # - id=4 (python, note, importance=3)
    ids = {lele["id"] for lele in results}
    assert ids == {"1", "4"}
