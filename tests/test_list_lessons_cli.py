from pathlib import Path

from lele_manager.cli.list_lessons import main as list_lessons_main
from lele_manager.model import Lesson
from lele_manager.storage import append_lesson

def test_list_lessons_filters_and_limit(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "lessons.jsonl"

    l1 = Lesson.new(
        source="chatgpt",
        topic="python",
        importance=5,
        text="Pytest layout src",
        tags=["python"],
    )
    l2 = Lesson.new(
        source="book",
        topic="ml",
        importance=3,
        text="Introduzione al ML",
        tags=["ml"],
    )
    l3 = Lesson.new(
        source="chatgpt",
        topic="ml",
        importance=4,
        text="Pytest e ML insieme",
        tags=["ml", "pytest"],
    )

    for lesson in (l1, l2, l3):
        append_lesson(lesson, db_path)

    argv = [
        "--db",
        str(db_path),
        "--source",
        "chatgpt",
        "--contains",
        "Pytest",
        "--limit",
        "10",
    ]

    list_lessons_main(argv)
    out = capsys.readouterr().out

    # Deve contenere l1 e l3 ma non l2
    assert "Pytest layout src" in out
    assert "Pytest e ML insieme" in out
    assert "Introduzione al ML" not in out

    # Summary finale coerente
    assert "2 lesson mostrate su 2 trovate" in out
