from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lele_manager.api import server


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_endpoint_contract_repeated_queries_limit_and_importance(
    tmp_path, monkeypatch
) -> None:
    data_path = tmp_path / "lessons.jsonl"
    _write_jsonl(
        data_path,
        [
            {
                "id": "z",
                "text": "Quiz Z",
                "topic": "python",
                "source": "book",
                "importance": 4,
                "tags": ["quiz"],
            },
            {
                "id": "a",
                "text": "Quiz A",
                "topic": "git",
                "source": "notes",
                "importance": 3,
                "tags": ["quiz", "review"],
            },
            {
                "id": "b",
                "text": "Quiz B",
                "topic": "rust",
                "source": "notes",
                "importance": 5,
                "tags": ["quiz"],
            },
        ],
    )
    monkeypatch.setattr(server, "DATA_PATH", data_path)

    response = TestClient(server.app).get(
        "/integrations/v1/lessons",
        params=[
            ("q", "quiz"),
            ("topic", "python"),
            ("topic", "git"),
            ("source", "book"),
            ("source", "notes"),
            ("tag", "quiz"),
            ("importance_gte", "3"),
            ("importance_lte", "4"),
            ("limit", "2"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 1
    assert payload["total_lessons"] == 3
    assert payload["returned_lessons"] == 2
    assert [lesson["id"] for lesson in payload["lessons"]] == ["a", "z"]
    assert set(payload["lessons"][0]) == {
        "id",
        "text",
        "title",
        "topic",
        "source",
        "importance",
        "tags",
        "date",
        "created_at",
    }
    assert payload["generation"].startswith("sha256:")


def test_empty_or_missing_projection_is_successful(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "DATA_PATH", tmp_path / "missing.jsonl")

    response = TestClient(server.app).get("/integrations/v1/lessons")

    assert response.status_code == 200
    assert response.json()["total_lessons"] == 0
    assert response.json()["returned_lessons"] == 0
    assert response.json()["lessons"] == []


def test_malformed_projection_returns_controlled_500(tmp_path, monkeypatch) -> None:
    data_path = tmp_path / "lessons.jsonl"
    data_path.write_text("not-json\n", encoding="utf-8")
    monkeypatch.setattr(server, "DATA_PATH", data_path)

    response = TestClient(server.app, raise_server_exceptions=False).get(
        "/integrations/v1/lessons"
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Lesson projection is unavailable."}
    assert "Jsonl" not in response.text
    assert "Traceback" not in response.text


def test_unreadable_projection_returns_controlled_500(monkeypatch) -> None:
    class UnreadableStore:
        def snapshot(self) -> object:
            raise OSError("private adapter details")

    monkeypatch.setattr(server, "projection_store", lambda path: UnreadableStore())

    with pytest.raises(HTTPException) as caught:
        server.integration_lessons(
            q=None,
            topic=None,
            source=None,
            tag=None,
            importance_gte=None,
            importance_lte=None,
            limit=None,
        )

    assert caught.value.status_code == 500
    assert caught.value.detail == "Lesson projection is unavailable."


def test_invalid_query_returns_422() -> None:
    client = TestClient(server.app)

    assert client.get("/integrations/v1/lessons?limit=0").status_code == 422
    assert client.get("/integrations/v1/lessons?importance_gte=nope").status_code == 422
