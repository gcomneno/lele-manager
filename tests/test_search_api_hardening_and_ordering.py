import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


@pytest.fixture()
def client(tmp_path: Path):
    data_path = tmp_path / "lele.jsonl"
    server.DATA_PATH = data_path
    c = TestClient(server.app)
    yield c, data_path
    server.DATA_PATH = None


def test_get_lessons_text_filter_does_not_match_nan_string(client):
    c, data_path = client
    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": None, "topic": None, "source": None, "importance": None, "tags": None, "date": None, "title": None},
            {"id": "2", "text": "banana", "topic": None, "source": None, "importance": 3, "tags": None, "date": "2025-01-01", "title": None},
        ],
    )

    r = c.get("/lessons", params={"q": "an", "limit": 50})
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert ids == ["2"]


def test_post_lessons_search_text_filter_does_not_match_nan_string(client):
    c, data_path = client
    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": None, "topic": None, "source": None, "importance": None, "tags": None, "date": None, "title": None},
            {"id": "2", "text": "banana", "topic": None, "source": None, "importance": 3, "tags": None, "date": "2025-01-01", "title": None},
        ],
    )

    r = c.post("/lessons/search", json={"q": "an", "limit": 50})
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert ids == ["2"]


def test_post_lessons_search_deterministic_ordering_importance_date_id(client):
    c, data_path = client
    _write_jsonl(
        data_path,
        [
            {"id": "a", "text": "A", "topic": None, "source": None, "importance": 5, "tags": None, "date": "2025-01-01", "title": None},
            {"id": "b", "text": "B", "topic": None, "source": None, "importance": 5, "tags": None, "date": "2026-01-01", "title": None},
            {"id": "c", "text": "C", "topic": None, "source": None, "importance": 4, "tags": None, "date": "2027-01-01", "title": None},
            {"id": "d", "text": "D", "topic": None, "source": None, "importance": 5, "tags": None, "date": None, "title": None},
        ],
    )

    r = c.post("/lessons/search", json={"limit": 10})
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    # importance DESC, date DESC, id ASC (date missing last among same importance)
    assert ids == ["b", "a", "d", "c"]
