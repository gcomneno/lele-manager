"""Canonical source-only lesson write primitive used by merge workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from lele_manager.core.lifecycle import LifecycleState
from lele_manager.core.vault import find_markdown_paths_by_id, write_lesson_markdown


class CanonicalLessonWriteError(Exception):
    pass


class CanonicalLessonWriteNotFoundError(CanonicalLessonWriteError):
    pass


class CanonicalLessonWriteAmbiguousError(CanonicalLessonWriteError):
    pass


class CanonicalLessonWriteStorageError(CanonicalLessonWriteError):
    pass


def write_canonical_lesson_source(
    *, vault_dir: Path, lesson_id: str, body: str, topic: str, source: str,
    importance: int, tags: list[str], date: str, title: str | None,
    lifecycle: LifecycleState, superseded_by: str | None,
    invalidate_cache: Callable[[], None],
) -> Path:
    """Rewrite exactly one existing canonical Markdown source without refresh."""
    matches = find_markdown_paths_by_id(vault_dir, lesson_id)
    if not matches:
        raise CanonicalLessonWriteNotFoundError("canonical lesson was not found")
    if len(matches) != 1:
        raise CanonicalLessonWriteAmbiguousError("canonical lesson identity is ambiguous")
    try:
        relative_path = matches[0].resolve().relative_to(vault_dir.resolve()).as_posix()
        result = write_lesson_markdown(
            vault_dir, lesson_id=lesson_id, body=body, topic=topic, source=source,
            importance=importance, tags=tags, date=date, title=title,
            relative_path=relative_path, lifecycle=lifecycle,
            superseded_by=superseded_by,
        )
    except (OSError, ValueError) as exc:
        raise CanonicalLessonWriteStorageError("canonical lesson could not be written") from exc
    invalidate_cache()
    return result
