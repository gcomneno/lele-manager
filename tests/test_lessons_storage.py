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

    loaded = load_lessons(db_path)
    assert len(loaded) == 1

    loaded_lesson = loaded[0]
    assert loaded_lesson.id == lesson.id
    assert loaded_lesson.source == "chatgpt"
    assert loaded_lesson.topic == "python"
    assert loaded_lesson.importance == 4
    assert loaded_lesson.text == "Una lesson di prova."
    assert "test" in loaded_lesson.tags
