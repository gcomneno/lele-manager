"""Application services for assistant-ready canonical context."""

from __future__ import annotations

from collections.abc import Sequence

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


def resolve_assistant_context_lesson_ids(
    *,
    lesson_ids: Sequence[str],
    context: ActiveVaultContext,
) -> tuple[CanonicalLessonSnapshot, ...]:
    """Resolve an explicit ordered lesson-ID scope canonically."""

    return tuple(
        read_canonical_lesson_snapshot(
            vault_dir=context.vault_dir,
            lesson_id=lesson_id,
        )
        for lesson_id in lesson_ids
    )


def resolve_assistant_context_pack(
    *,
    pack_id: str,
    context: ActiveVaultContext,
    store: ContextPackStore,
) -> tuple[CanonicalLessonSnapshot, ...]:
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

    return tuple(
        member.lesson
        for member in resolved.members
        if member.lesson is not None
    )
