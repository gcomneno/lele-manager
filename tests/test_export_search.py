from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.core.export import lesson_to_markdown_block, search_results_to_markdown


def _write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_lesson_to_markdown_with_frontmatter() -> None:
    lesson = {
        "id": "python/2025-01-01.pytest",
        "text": "Corpo con emoji: caffè ☕",
        "topic": "python",
        "source": "note",
        "importance": 4,
        "tags": ["pytest", "python"],
        "date": "2025-01-01",
        "title": "Pytest tips",
    }
    md = lesson_to_markdown_block(lesson, include_frontmatter=True)
    assert md.startswith("---\n")
    assert "id: python/2025-01-01.pytest" in md
    assert "tags:" in md
    assert "caffè ☕" in md


def test_lesson_to_markdown_without_frontmatter() -> None:
    lesson = {"id": "x", "text": "solo body", "title": "Titolo"}
    md = lesson_to_markdown_block(lesson, include_frontmatter=False)
    assert md.startswith("## Titolo")
    assert "solo body" in md
    assert not md.startswith("---")


def test_export_search_markdown_and_json(tmp_path, monkeypatch) -> None:
    data_path = tmp_path / "lessons.jsonl"
    records = [
        {
            "id": "1",
            "text": "LeLe su pytest e Python",
            "topic": "python",
            "source": "note",
            "importance": 4,
            "tags": ["python", "pytest"],
        },
        {
            "id": "2",
            "text": "LeLe su Git",
            "topic": "git",
            "source": "note",
            "importance": 3,
            "tags": ["git"],
        },
    ]
    _write_jsonl(data_path, records)
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)

    client = TestClient(server.app)

    r_md = client.post(
        "/export/search",
        params={"format": "markdown"},
        json={"q": "pytest", "limit": 10, "include_frontmatter": True},
    )
    assert r_md.status_code == 200
    assert r_md.headers["content-type"].startswith("text/markdown")
    text = r_md.content.decode("utf-8")
    assert "# LeLe export" in text
    assert "pytest" in text
    assert "id: 1" in text or 'id: "1"' in text or "id: '1'" in text

    r_json = client.post(
        "/export/search",
        params={"format": "json"},
        json={"q": "pytest", "limit": 10},
    )
    assert r_json.status_code == 200
    payload = r_json.json()
    assert payload["n_lessons"] == 1
    assert "pytest" in payload["markdown"]


def test_export_search_ids_in_filter(tmp_path, monkeypatch) -> None:
    data_path = tmp_path / "lessons.jsonl"
    records = [
        {"id": "a", "text": "alpha", "topic": "t"},
        {"id": "b", "text": "beta", "topic": "t"},
    ]
    _write_jsonl(data_path, records)
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)

    client = TestClient(server.app)
    r = client.post(
        "/export/search",
        params={"format": "json"},
        json={"limit": 10, "ids_in": ["b"]},
    )
    assert r.status_code == 200
    assert r.json()["n_lessons"] == 1
    assert "beta" in r.json()["markdown"]


def test_search_results_to_markdown_empty() -> None:
    md = search_results_to_markdown([], include_frontmatter=True, filters_summary="q='x'")
    assert "Nessuna LeLe" in md
