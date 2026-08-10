"""Delete one canonical lesson, then reconcile its derived projection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lele_manager.application.candidate_approval import RefreshOutcome
from lele_manager.core.vault import find_markdown_by_id


@dataclass(frozen=True)
class LessonDeletionResult:
    lesson_id: str
    relative_vault_path: str
    canonical_deleted: Literal[True]
    refresh_outcome: RefreshOutcome


class LessonDeletionError(Exception):
    """Base class for controlled single-lesson deletion failures."""


class LessonDeletionNotFoundError(LessonDeletionError):
    pass


class LessonDeletionStorageError(LessonDeletionError):
    pass


class PartialLessonDeletionRefreshError(LessonDeletionError):
    """The Markdown deletion succeeded, but derived reconciliation did not."""

    def __init__(self, result: LessonDeletionResult) -> None:
        self.result = result
        super().__init__(
            "canonical lesson was deleted but derived projection refresh failed"
        )


def delete_canonical_lesson(
    *,
    vault_dir: Path,
    lesson_id: str,
    refresh: Callable[[], object],
    invalidate_cache: Callable[[], None],
) -> LessonDeletionResult:
    """Delete exactly one resolved Markdown lesson before refreshing derivatives."""
    markdown_path = find_markdown_by_id(vault_dir, lesson_id)
    if markdown_path is None:
        raise LessonDeletionNotFoundError("canonical lesson was not found")

    vault_root = vault_dir.resolve()
    resolved_path = markdown_path.resolve()
    try:
        relative_path = resolved_path.relative_to(vault_root).as_posix()
    except ValueError as exc:
        raise LessonDeletionStorageError("refusing to delete outside the vault") from exc

    try:
        resolved_path.unlink()
    except OSError as exc:
        raise LessonDeletionStorageError("canonical lesson could not be deleted") from exc

    # Clearing the in-memory index now prevents a prior cache from continuing
    # to serve a lesson that no longer exists in the source of truth.
    invalidate_cache()
    result = LessonDeletionResult(
        lesson_id=lesson_id,
        relative_vault_path=relative_path,
        canonical_deleted=True,
        refresh_outcome=RefreshOutcome(refreshed=True),
    )
    try:
        refresh()
    except Exception as exc:
        raise PartialLessonDeletionRefreshError(result) from exc
    return result
