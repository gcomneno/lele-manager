"""Canonical lesson deletion primitives and single-delete compatibility API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lele_manager.application.candidate_approval import RefreshOutcome
from lele_manager.core.canonical_mutation import canonical_mutation_boundary
from lele_manager.core.vault import find_markdown_paths_by_id


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


@dataclass(frozen=True)
class CanonicalLessonDeletionResult:
    """A source-of-truth deletion completed before derived reconciliation."""

    lesson_id: str
    relative_vault_path: str
    canonical_deleted: Literal[True] = True


def delete_canonical_lesson_source(
    *,
    vault_dir: Path,
    lesson_id: str,
    invalidate_cache: Callable[[], None],
) -> CanonicalLessonDeletionResult:
    """Resolve and unlink exactly one in-vault Markdown source safely.

    This intentionally performs no projection refresh so a batch can reconcile
    the real final vault state exactly once.
    """
    with canonical_mutation_boundary():
        matches = find_markdown_paths_by_id(vault_dir, lesson_id)
        if not matches:
            raise LessonDeletionNotFoundError("canonical lesson was not found")
        if len(matches) != 1:
            raise LessonDeletionStorageError("canonical lesson identity is ambiguous")
        markdown_path = matches[0]

        vault_root = vault_dir.resolve()
        resolved_path = markdown_path.resolve()
        try:
            relative_path = resolved_path.relative_to(vault_root).as_posix()
        except ValueError as exc:
            raise LessonDeletionStorageError(
                "refusing to delete outside the vault"
            ) from exc

        try:
            resolved_path.unlink()
        except OSError as exc:
            raise LessonDeletionStorageError(
                "canonical lesson could not be deleted"
            ) from exc

    # Do this immediately: a stale in-memory similarity index must never keep
    # a deleted canonical source alive until a later request.
    invalidate_cache()
    return CanonicalLessonDeletionResult(
        lesson_id=lesson_id,
        relative_vault_path=relative_path,
    )


def delete_canonical_lesson(
    *,
    vault_dir: Path,
    lesson_id: str,
    refresh: Callable[[], object],
    invalidate_cache: Callable[[], None],
) -> LessonDeletionResult:
    """Delete exactly one resolved Markdown lesson before refreshing derivatives."""
    canonical_result = delete_canonical_lesson_source(
        vault_dir=vault_dir,
        lesson_id=lesson_id,
        invalidate_cache=invalidate_cache,
    )
    result = LessonDeletionResult(
        lesson_id=canonical_result.lesson_id,
        relative_vault_path=canonical_result.relative_vault_path,
        canonical_deleted=True,
        refresh_outcome=RefreshOutcome(refreshed=True),
    )
    try:
        refresh()
    except Exception as exc:
        raise PartialLessonDeletionRefreshError(result) from exc
    return result
