from __future__ import annotations

from pathlib import Path

from lele_manager.cli.add_lesson import main as add_lesson_main
from lele_manager.storage import load_lessons

import io
import sys
import pytest

def test_add_lesson_cli_writes_to_db(tmp_path: Path) -> None:
    db_path = tmp_path / "lessons.jsonl"

    argv = [
        "--text",
        "Lesson from CLI",
        "--source",
        "chatgpt",
        "--topic",
        "python",
        "--importance",
        "5",
        "--tags",
        "python,cli",
        "--db",
        str(db_path),
    ]

    add_lesson_main(argv)

    lessons = load_lessons(db_path)
    assert len(lessons) == 1

    lessons = load_lessons(db_path)
    assert len(lessons) == 1

    saved_lesson = lessons[0]
    assert saved_lesson.text == "Lesson from CLI"
    assert saved_lesson.source == "chatgpt"
    assert saved_lesson.topic == "python"
    assert saved_lesson.importance == 5
    assert saved_lesson.tags == ["python", "cli"]

def test_add_lesson_cli_invalid_importance(tmp_path: Path) -> None:
    db_path = tmp_path / "lessons.jsonl"

    argv = [
        "--text",
        "Lesson con importance fuori range",
        "--importance",
        "99",
        "--db",
        str(db_path),
    ]

    with pytest.raises(SystemExit):
        add_lesson_main(argv)

    # non deve aver creato il DB
    assert not db_path.exists()

def test_add_lesson_cli_reads_from_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "lessons.jsonl"

    # Simuliamo stdin con una StringIO
    fake_stdin = io.StringIO("Lesson da stdin\nSeconda riga")
    monkeypatch.setattr(sys, "stdin", fake_stdin)

    argv = [
        "--source",
        "chatgpt",
        "--topic",
        "python",
        "--importance",
        "3",
        "--db",
        str(db_path),
    ]

    add_lesson_main(argv)

    lessons = load_lessons(db_path)
    assert len(lessons) == 1
    assert "Lesson da stdin" in lessons[0].text
    assert "Seconda riga" in lessons[0].text
    assert lessons[0].source == "chatgpt"
    assert lessons[0].topic == "python"
    assert lessons[0].importance == 3
