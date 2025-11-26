from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import json

from .model import Lesson

DEFAULT_DB_PATH = Path("data/lessons.jsonl")

def default_db_path() -> Path:
    """Percorso di default del file JSONL."""
    return DEFAULT_DB_PATH

def append_lesson(lesson: Lesson, db_path: Path | None = None) -> None:
    """Aggiunge una lesson al file JSONL (una riga = un record JSON)."""
    if db_path is None:
        db_path = default_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(lesson.to_dict(), ensure_ascii=False)
    with db_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_lessons(db_path: Path | None = None) -> List[Lesson]:
    """Carica tutte le lesson dal file JSONL; se non esiste, ritorna lista vuota."""
    if db_path is None:
        db_path = default_db_path()

    if not db_path.exists():
        return []

    lessons: List[Lesson] = []
    with db_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            lessons.append(Lesson.from_dict(data))
    return lessons

def iter_lessons(db_path: Path | None = None) -> Iterable[Lesson]:
    """Iteratore lazy sulle lesson (per futuri usi su file grandi)."""
    if db_path is None:
        db_path = default_db_path()

    if not db_path.exists():
        return

    with db_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            yield Lesson.from_dict(data)
