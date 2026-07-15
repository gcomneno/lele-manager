from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from lele_manager.composition import legacy_jsonl_append_facade, projection_store
from .model import Lesson
from .paths import lessons_path


def default_db_path() -> Path:
    """Percorso di default del file JSONL (XDG via platformdirs)."""
    return lessons_path()


def append_lesson(lesson: Lesson, db_path: Path | None = None) -> None:
    """Aggiunge una lesson al file JSONL (una riga = un record JSON)."""
    if db_path is None:
        db_path = default_db_path()

    legacy_jsonl_append_facade(db_path).append(lesson.to_dict())


def load_lessons(db_path: Path | None = None) -> List[Lesson]:
    """Carica tutte le lesson dal file JSONL; se non esiste, ritorna lista vuota."""
    if db_path is None:
        db_path = default_db_path()

    return [Lesson.from_dict(dict(row)) for row in projection_store(db_path).snapshot().list()]


def iter_lessons(db_path: Path | None = None) -> Iterable[Lesson]:
    """Iteratore lazy sulle lesson (per futuri usi su file grandi)."""
    if db_path is None:
        db_path = default_db_path()

    for row in projection_store(db_path).snapshot().list():
        yield Lesson.from_dict(dict(row))
