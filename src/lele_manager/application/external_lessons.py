"""Stable, backend-neutral lesson feed for external integrations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any, Literal

from lele_manager.core.projection_store import LessonQuery, ProjectionStore


@dataclass(frozen=True)
class ExternalLesson:
    """The deliberately small public representation of one lesson."""

    id: str
    text: str
    title: str | None
    topic: str | None
    source: str | None
    importance: int | None
    tags: list[str]
    date: str | None
    created_at: str | None


@dataclass(frozen=True)
class ExternalLessonsFeed:
    """Versioned response contract exposed to external read-only consumers."""

    schema_version: Literal[1]
    generation: str
    total_lessons: int
    returned_lessons: int
    lessons: list[ExternalLesson]


def _scalar_string(value: object) -> str | None:
    if (
        value is None
        or isinstance(value, (Mapping, Sequence))
        and not isinstance(value, str)
    ):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        return str(value)
    except (TypeError, ValueError):
        return None


def _importance(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _tags(value: object) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        return []
    normalized = {
        item
        for raw_item in value
        if (item := _scalar_string(raw_item)) is not None and item
    }
    return sorted(normalized)


def _normalize_lesson(record: Mapping[str, Any]) -> ExternalLesson:
    return ExternalLesson(
        id=_scalar_string(record.get("id")) or "",
        text=_scalar_string(record.get("text")) or "",
        title=_scalar_string(record.get("title")),
        topic=_scalar_string(record.get("topic")),
        source=_scalar_string(record.get("source")),
        importance=_importance(record.get("importance")),
        tags=_tags(record.get("tags")),
        date=_scalar_string(record.get("date")),
        created_at=_scalar_string(record.get("created_at")),
    )


def external_lessons_feed(
    store: ProjectionStore,
    query: LessonQuery,
) -> ExternalLessonsFeed:
    """Read and normalize a feed from one coherent projection snapshot."""
    snapshot = store.snapshot()
    records = snapshot.list(query)
    lessons = [_normalize_lesson(record) for record in records]
    return ExternalLessonsFeed(
        schema_version=1,
        generation=snapshot.generation,
        total_lessons=snapshot.statistics.lesson_count,
        returned_lessons=len(lessons),
        lessons=lessons,
    )
