from datetime import datetime, timezone

from lele_manager.model import Lesson

def test_lesson_roundtrip_to_from_dict() -> None:
    lesson = Lesson.new(
        source="chatgpt",
        topic="python",
        importance=4,
        text="Lesson di prova per il roundtrip.",
        tags=["python", "pytest"],
    )

    data = lesson.to_dict()

    # id e created_at devono essere presenti e sensati
    assert data["id"] == lesson.id
    assert isinstance(data["created_at"], str)
    assert data["created_at"].endswith("+00:00")

    # ricostruiamo una Lesson e deve essere uguale (dataclass equality)
    lesson2 = Lesson.from_dict(data)
    assert lesson2 == lesson

def test_lesson_from_dict_defaults() -> None:
    now = datetime.now(timezone.utc)
    data = {
        "id": "42",
        "created_at": now.isoformat(),
        "text": "Solo testo, il resto con default.",
    }

    lesson = Lesson.from_dict(data)

    assert lesson.id == "42"
    assert lesson.text == "Solo testo, il resto con default."
    assert lesson.source == ""
    assert lesson.topic == ""
    assert lesson.importance == 0
    assert lesson.tags == []
