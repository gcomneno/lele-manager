from pathlib import Path

from lele_manager.model import Lesson
from lele_manager.storage import append_lesson, load_lessons

def test_append_and_load_lessons(tmp_path: Path) -> None:
    db_path = tmp_path / "lessons.jsonl"

    lesson = Lesson.new(
        source="chatgpt",
        topic="python",
        importance=4,
        text="Una lesson di prova.",
        tags=["test", "example"],
    )

    append_lesson(lesson, db_path)

    loaded = load_lessons(db_path)
    assert len(loaded) == 1

    l = loaded[0]
    assert l.id == lesson.id
    assert l.source == "chatgpt"
    assert l.topic == "python"
    assert l.importance == 4
    assert l.text == "Una lesson di prova."
    assert "test" in l.tags
