"""Application services for resolving Context Pack references."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lele_manager.application.lesson_writing import (
    CanonicalLessonSnapshot,
    CanonicalLessonWriteNotFoundError,
    read_canonical_lesson_snapshot,
)
from lele_manager.core.context_pack_store import ContextPack, ContextPackStore
from lele_manager.core.vault_registry import ActiveVaultContext


@dataclass(frozen=True, slots=True)
class ContextPackMember:
    lesson_id: str
    position: int
    resolved: bool
    lesson: CanonicalLessonSnapshot | None


@dataclass(frozen=True, slots=True)
class ResolvedContextPack:
    pack: ContextPack
    members: tuple[ContextPackMember, ...]


def create_context_pack(
    *,
    name: str,
    lesson_ids: tuple[str, ...],
    context: ActiveVaultContext,
    store: ContextPackStore,
) -> ContextPack:
    """Create a pack only when every requested member resolves canonically."""
    for lesson_id in lesson_ids:
        read_canonical_lesson_snapshot(
            vault_dir=context.vault_dir,
            lesson_id=lesson_id,
        )

    return store.create(
        name=name,
        vault_id=context.vault_id,
        lesson_ids=lesson_ids,
    )


def add_context_pack_members(
    *,
    pack_id: str,
    lesson_ids: tuple[str, ...],
    context: ActiveVaultContext,
    store: ContextPackStore,
) -> ContextPack:
    """Add members only after the entire batch resolves canonically."""
    for lesson_id in lesson_ids:
        read_canonical_lesson_snapshot(
            vault_dir=context.vault_dir,
            lesson_id=lesson_id,
        )

    return store.add_members(
        pack_id,
        vault_id=context.vault_id,
        lesson_ids=lesson_ids,
    )


def get_resolved_context_pack(
    *,
    pack_id: str,
    context: ActiveVaultContext,
    store: ContextPackStore,
) -> ResolvedContextPack:
    """Load and resolve one pack inside one coherent Vault context."""
    pack = store.get(
        pack_id,
        vault_id=context.vault_id,
    )
    return resolve_context_pack(
        pack=pack,
        vault_dir=context.vault_dir,
    )


def resolve_context_pack(
    *,
    pack: ContextPack,
    vault_dir: Path,
) -> ResolvedContextPack:
    """Resolve one pack against the current canonical Vault state.

    Missing canonical lessons remain explicit unresolved references. Canonical
    ambiguity and storage/integrity failures deliberately propagate.
    """
    members: list[ContextPackMember] = []

    for position, lesson_id in enumerate(pack.lesson_ids):
        try:
            lesson = read_canonical_lesson_snapshot(
                vault_dir=vault_dir,
                lesson_id=lesson_id,
            )
        except CanonicalLessonWriteNotFoundError:
            members.append(
                ContextPackMember(
                    lesson_id=lesson_id,
                    position=position,
                    resolved=False,
                    lesson=None,
                )
            )
            continue

        members.append(
            ContextPackMember(
                lesson_id=lesson_id,
                position=position,
                resolved=True,
                lesson=lesson,
            )
        )

    return ResolvedContextPack(
        pack=pack,
        members=tuple(members),
    )
