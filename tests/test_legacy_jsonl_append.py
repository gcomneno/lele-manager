import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from lele_manager.api import server
from lele_manager.cli import add_lesson
from lele_manager.composition import legacy_jsonl_append_facade, projection_store
from lele_manager.core.model import Lesson
from lele_manager.core.projection_store import DuplicateLessonIdError, MalformedProjectionError


def test_duplicate_append_rejected_without_changing_bytes(tmp_path: Path) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_bytes(b'{"id":"same","text":"old"}\n')
    before = path.read_bytes()
    with pytest.raises(DuplicateLessonIdError, match="same"):
        legacy_jsonl_append_facade(path).append({"id": "same", "text": "new"})
    assert path.read_bytes() == before


def test_malformed_existing_dataset_rejected_without_changing_bytes(tmp_path: Path) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_bytes(b'{"id":"ok"}\nnot-json\n')
    before = path.read_bytes()
    with pytest.raises(MalformedProjectionError, match="line 2"):
        legacy_jsonl_append_facade(path).append({"id": "new"})
    assert path.read_bytes() == before


def test_append_after_valid_final_line_without_newline_stays_readable(tmp_path: Path) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_bytes(b'{"id":"old"}')
    facade = legacy_jsonl_append_facade(path)
    facade.append({"id": "new"})
    assert [row["id"] for row in projection_store(path).snapshot().list()] == ["old", "new"]


def test_api_duplicate_append_is_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_text('{"id":"same","text":"old"}\n', encoding="utf-8")
    monkeypatch.setattr(server, "DATA_PATH", path)
    with pytest.raises(HTTPException) as raised:
        server.add_lesson(server.LessonCreate(id="same", text="new"))
    assert raised.value.status_code == 409
    assert raised.value.detail == "Lesson ID già esistente: same"


def test_api_malformed_dataset_is_actionable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    monkeypatch.setattr(server, "DATA_PATH", path)
    with pytest.raises(HTTPException) as raised:
        server.add_lesson(server.LessonCreate(id="new", text="new"))
    assert raised.value.status_code == 409
    assert "append annullato" in str(raised.value.detail)
    assert "line 1" in str(raised.value.detail)


def test_legacy_cli_reports_malformed_dataset(tmp_path: Path) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Impossibile aggiungere.*line 1"):
        add_lesson.main(["--text", "new", "--db", str(path)])


def test_legacy_cli_reports_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "lessons.jsonl"
    existing = Lesson.new(source="note", topic="misc", importance=3, text="old", tags=[])
    path.write_text(json.dumps(existing.to_dict()) + "\n", encoding="utf-8")
    monkeypatch.setattr(add_lesson.Lesson, "new", lambda **kwargs: existing)
    with pytest.raises(SystemExit, match="duplicate lesson id"):
        add_lesson.main(["--text", "new", "--db", str(path)])
