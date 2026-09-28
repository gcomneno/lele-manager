from __future__ import annotations

from pathlib import Path

import pytest

from lele_manager.api import server
from lele_manager.application.assistant_context import (
    AssistantContextBrokenReferencesError,
    ResolvedAssistantContext,
    resolve_assistant_context_lesson_ids,
    resolve_assistant_context_pack,
)
from lele_manager.core.context_pack_store import ContextPackStore
from lele_manager.core.vault import write_lesson_markdown
from lele_manager.core.vault_registry import ActiveVaultContext


def _context(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )
    return server.get_active_vault_context()


def _write(
    context: ActiveVaultContext,
    lesson_id: str,
    *,
    body: str,
) -> None:
    write_lesson_markdown(
        context.vault_dir,
        lesson_id=lesson_id,
        body=body,
        topic=lesson_id.split("/", 1)[0],
        source="test",
        importance=3,
        tags=["assistant"],
        date="2026-09-28",
        title=lesson_id,
    )


def test_resolved_context_uses_canonical_lessons_as_citation_authority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path, monkeypatch)

    _write(context, "python/bravo", body="Canonical bravo.")
    _write(context, "python/alpha", body="Canonical alpha.")

    resolved = resolve_assistant_context_lesson_ids(
        lesson_ids=(
            "python/bravo",
            "python/alpha",
        ),
        context=context,
    )

    assert isinstance(resolved, ResolvedAssistantContext)
    assert resolved.lesson_ids == (
        "python/bravo",
        "python/alpha",
    )
    assert tuple(
        lesson.text
        for lesson in resolved.lessons
    ) == (
        "Canonical bravo.",
        "Canonical alpha.",
    )


def test_context_pack_uses_same_resolved_context_boundary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path, monkeypatch)

    _write(context, "python/bravo", body="Bravo.")
    _write(context, "python/alpha", body="Alpha.")

    store = ContextPackStore(tmp_path / "context-packs.json")
    pack = store.create(
        name="Ask scope",
        vault_id=context.vault_id,
        lesson_ids=(
            "python/bravo",
            "python/alpha",
        ),
    )

    resolved = resolve_assistant_context_pack(
        pack_id=pack.id,
        context=context,
        store=store,
    )

    assert resolved.lesson_ids == (
        "python/bravo",
        "python/alpha",
    )


def test_context_pack_never_silently_drops_broken_citation_authority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path, monkeypatch)

    _write(context, "python/current", body="Current.")

    store = ContextPackStore(tmp_path / "context-packs.json")
    pack = store.create(
        name="Broken",
        vault_id=context.vault_id,
        lesson_ids=(
            "python/current",
            "python/missing",
        ),
    )

    with pytest.raises(
        AssistantContextBrokenReferencesError,
    ) as exc_info:
        resolve_assistant_context_pack(
            pack_id=pack.id,
            context=context,
            store=store,
        )

    assert exc_info.value.lesson_ids == (
        "python/missing",
    )
