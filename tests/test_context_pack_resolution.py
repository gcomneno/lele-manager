from __future__ import annotations

from pathlib import Path

import pytest

from lele_manager.application.context_packs import resolve_context_pack
from lele_manager.application.lesson_writing import (
    CanonicalLessonWriteAmbiguousError,
)
from lele_manager.core.context_pack_store import ContextPackStore
from lele_manager.core.vault import write_lesson_markdown


VAULT_ID = "11111111-1111-4111-8111-111111111111"


def _write_lesson(
    vault: Path,
    lesson_id: str,
    *,
    body: str,
    lifecycle: str = "active",
) -> None:
    topic = lesson_id.split("/", 1)[0]
    write_lesson_markdown(
        vault,
        lesson_id=lesson_id,
        body=body,
        topic=topic,
        source="test",
        importance=3,
        tags=["context-pack"],
        date="2026-09-19",
        title=lesson_id,
        lifecycle=lifecycle,
    )


def test_resolve_preserves_pack_order_and_reads_current_canonical_state(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    store = ContextPackStore(tmp_path / "context-packs.json")

    _write_lesson(
        vault,
        "python/old",
        body="Deprecated canonical lesson.",
        lifecycle="deprecated",
    )
    _write_lesson(
        vault,
        "git/current",
        body="Current canonical lesson.",
    )

    pack = store.create(
        name="Release investigation",
        vault_id=VAULT_ID,
        lesson_ids=("git/current", "python/old"),
    )

    resolved = resolve_context_pack(
        pack=pack,
        vault_dir=vault,
    )

    assert resolved.pack == pack
    assert [member.lesson_id for member in resolved.members] == [
        "git/current",
        "python/old",
    ]

    current, old = resolved.members

    assert current.position == 0
    assert current.resolved is True
    assert current.lesson is not None
    assert current.lesson.text == "Current canonical lesson."
    assert current.lesson.lifecycle == "active"

    assert old.position == 1
    assert old.resolved is True
    assert old.lesson is not None
    assert old.lesson.text == "Deprecated canonical lesson."
    assert old.lesson.lifecycle == "deprecated"


def test_resolve_reports_missing_reference_without_dropping_it(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    store = ContextPackStore(tmp_path / "context-packs.json")

    _write_lesson(vault, "git/current", body="Current canonical lesson.")

    pack = store.create(
        name="Broken reference",
        vault_id=VAULT_ID,
        lesson_ids=("git/current", "python/missing"),
    )

    resolved = resolve_context_pack(
        pack=pack,
        vault_dir=vault,
    )

    assert [member.lesson_id for member in resolved.members] == [
        "git/current",
        "python/missing",
    ]

    missing = resolved.members[1]
    assert missing.position == 1
    assert missing.resolved is False
    assert missing.lesson is None


def test_resolve_does_not_hide_ambiguous_canonical_identity(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    store = ContextPackStore(tmp_path / "context-packs.json")

    _write_lesson(vault, "python/duplicate", body="First.")

    duplicate = vault / "other" / "duplicate.md"
    duplicate.parent.mkdir(parents=True, exist_ok=True)
    duplicate.write_text(
        """---
id: python/duplicate
topic: other
source: test
importance: 3
tags:
  - context-pack
date: 2026-09-19
title: Duplicate
---

Second.
""",
        encoding="utf-8",
    )

    pack = store.create(
        name="Ambiguous reference",
        vault_id=VAULT_ID,
        lesson_ids=("python/duplicate",),
    )

    with pytest.raises(CanonicalLessonWriteAmbiguousError):
        resolve_context_pack(
            pack=pack,
            vault_dir=vault,
        )


def test_get_resolved_pack_uses_one_coherent_vault_context(
    tmp_path: Path,
) -> None:
    from lele_manager.application.context_packs import get_resolved_context_pack
    from lele_manager.core.vault_registry import ActiveVaultContext

    vault = tmp_path / "vault"
    store = ContextPackStore(tmp_path / "context-packs.json")

    _write_lesson(
        vault,
        "python/current",
        body="Canonical state from the scoped Vault.",
    )

    pack = store.create(
        name="Scoped pack",
        vault_id=VAULT_ID,
        lesson_ids=("python/current",),
    )

    context = ActiveVaultContext(
        vault_id=VAULT_ID,
        display_name="Primary",
        vault_dir=vault,
        projection_path=tmp_path / "projection.jsonl",
        candidates_path=tmp_path / "candidates.json",
        topic_model_path=tmp_path / "topic-model.pkl",
        duplicate_decision_scope="vault:test",
    )

    resolved = get_resolved_context_pack(
        pack_id=pack.id,
        context=context,
        store=store,
    )

    assert resolved.pack == pack
    assert len(resolved.members) == 1
    assert resolved.members[0].resolved is True
    assert resolved.members[0].lesson is not None
    assert (
        resolved.members[0].lesson.text
        == "Canonical state from the scoped Vault."
    )


def test_get_resolved_pack_rejects_pack_from_another_vault(
    tmp_path: Path,
) -> None:
    from lele_manager.application.context_packs import get_resolved_context_pack
    from lele_manager.core.context_pack_store import ContextPackNotFoundError
    from lele_manager.core.vault_registry import ActiveVaultContext

    store = ContextPackStore(tmp_path / "context-packs.json")

    pack = store.create(
        name="Vault A pack",
        vault_id=VAULT_ID,
        lesson_ids=("python/current",),
    )

    other_vault_id = "22222222-2222-4222-8222-222222222222"
    other_vault = tmp_path / "other-vault"
    _write_lesson(
        other_vault,
        "python/current",
        body="Same ID, wrong Vault.",
    )

    context = ActiveVaultContext(
        vault_id=other_vault_id,
        display_name="Other",
        vault_dir=other_vault,
        projection_path=tmp_path / "other-projection.jsonl",
        candidates_path=tmp_path / "other-candidates.json",
        topic_model_path=tmp_path / "other-topic-model.pkl",
        duplicate_decision_scope="vault:other",
    )

    with pytest.raises(ContextPackNotFoundError):
        get_resolved_context_pack(
            pack_id=pack.id,
            context=context,
            store=store,
        )
