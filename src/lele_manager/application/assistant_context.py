"""Application services for assistant-ready canonical context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lele_manager.application.context_packs import (
    get_resolved_context_pack,
)
from lele_manager.application.lesson_writing import (
    CanonicalLessonSnapshot,
    read_canonical_lesson_snapshot,
)
from lele_manager.core.context_pack_store import ContextPackStore
from lele_manager.core.vault_registry import ActiveVaultContext


class AssistantContextBrokenReferencesError(Exception):
    def __init__(self, lesson_ids: tuple[str, ...]) -> None:
        self.lesson_ids = lesson_ids
        super().__init__(
            "assistant context contains missing canonical references"
        )


@dataclass(frozen=True, slots=True)
class ResolvedAssistantContext:
    """One ordered canonical grounding scope.

    This is the maintained authority boundary shared by assistant-ready export
    and conversational consumers. Search/ranking may choose identity and order,
    but lesson content is always read again from canonical Markdown.
    """

    lessons: tuple[CanonicalLessonSnapshot, ...]

    @property
    def lesson_ids(self) -> tuple[str, ...]:
        return tuple(lesson.lesson_id for lesson in self.lessons)


def resolve_assistant_context_lesson_ids(
    *,
    lesson_ids: Sequence[str],
    context: ActiveVaultContext,
) -> ResolvedAssistantContext:
    """Resolve an explicit ordered lesson-ID scope canonically."""

    lessons = tuple(
        read_canonical_lesson_snapshot(
            vault_dir=context.vault_dir,
            lesson_id=lesson_id,
        )
        for lesson_id in lesson_ids
    )

    return ResolvedAssistantContext(lessons=lessons)


def resolve_assistant_context_pack(
    *,
    pack_id: str,
    context: ActiveVaultContext,
    store: ContextPackStore,
) -> ResolvedAssistantContext:
    """Resolve one Context Pack without silently dropping broken refs."""

    resolved = get_resolved_context_pack(
        pack_id=pack_id,
        context=context,
        store=store,
    )

    missing = tuple(
        member.lesson_id
        for member in resolved.members
        if not member.resolved
    )
    if missing:
        raise AssistantContextBrokenReferencesError(missing)

    lessons = tuple(
        member.lesson
        for member in resolved.members
        if member.lesson is not None
    )

    return ResolvedAssistantContext(lessons=lessons)
