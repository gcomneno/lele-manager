from lele_manager.application.lesson_writing import (
    CanonicalLessonWriteHistoryError,
    CanonicalLessonWriteStaleError,
    diff_lesson_revisions,
    read_canonical_lesson_revision,
    rollback_canonical_lesson_source,
    write_revisioned_canonical_lesson_source,
)
from lele_manager.core.vault import write_lesson_markdown
from datetime import datetime, timezone
from pathlib import Path

import pytest

import lele_manager.core.lesson_revision_history as revision_history
from lele_manager.core.lesson_revision_history import (
    LessonRevision,
    LessonRevisionHistoryConflictError,
    LessonRevisionHistoryError,
    LessonRevisionHistoryStore,
    canonical_fingerprint,
)


def revision(
    lesson_id: str,
    number: int,
    markdown: str,
    *,
    action: str,
    rollback_from: int | None = None,
) -> LessonRevision:
    return LessonRevision(
        lesson_id=lesson_id,
        revision=number,
        canonical_fingerprint=canonical_fingerprint(markdown.encode("utf-8")),
        occurred_at=datetime(2026, 8, 15, tzinfo=timezone.utc).isoformat(),
        action=action,  # type: ignore[arg-type]
        relative_path=f"{lesson_id}.md",
        markdown=markdown,
        rollback_from_revision=rollback_from,
    )


def test_exact_canonical_fingerprint_preserves_byte_differences() -> None:
    assert canonical_fingerprint(b"body\n") != canonical_fingerprint(b"body\r\n")
    assert canonical_fingerprint(b"body") != canonical_fingerprint(b"body ")


def test_history_starts_with_baseline_and_is_monotonic(tmp_path: Path) -> None:
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    baseline = revision("python/example", 0, "before\n", action="baseline")
    edited = revision("python/example", 1, "after\n", action="edit")

    store.append(baseline)
    store.append(edited)

    assert store.list("python/example") == (baseline, edited)
    assert store.get("python/example", 1) == edited


def test_rollback_can_repeat_an_older_fingerprint_as_a_new_revision(
    tmp_path: Path,
) -> None:
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    baseline = revision("python/example", 0, "A\n", action="baseline")
    edited = revision("python/example", 1, "B\n", action="edit")
    rolled_back = revision(
        "python/example",
        2,
        "A\n",
        action="rollback",
        rollback_from=0,
    )

    for item in (baseline, edited, rolled_back):
        store.append(item)

    assert rolled_back.revision == 2
    assert rolled_back.canonical_fingerprint == baseline.canonical_fingerprint
    assert store.list("python/example")[-1] == rolled_back


def test_append_rejects_gaps_and_second_baseline(tmp_path: Path) -> None:
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")
    store.append(revision("python/example", 0, "A", action="baseline"))

    with pytest.raises(LessonRevisionHistoryConflictError):
        store.append(revision("python/example", 2, "C", action="edit"))

    with pytest.raises(LessonRevisionHistoryConflictError):
        store.append(revision("python/example", 1, "B", action="baseline"))


def test_malformed_or_tampered_history_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "lesson-revisions.json"
    path.write_text(
        """
{
  "schema_version": 1,
  "lessons": {
    "python/example": [{
      "revision": 0,
      "canonical_fingerprint": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "occurred_at": "2026-08-15T00:00:00+00:00",
      "action": "baseline",
      "relative_path": "python/example.md",
      "markdown": "different",
      "reason": null,
      "rollback_from_revision": null
    }]
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LessonRevisionHistoryError, match="fingerprint"):
        LessonRevisionHistoryStore(path).list("python/example")


def test_histories_are_isolated_by_scoped_store_path(tmp_path: Path) -> None:
    first = LessonRevisionHistoryStore(
        tmp_path / "vaults" / "vault-a" / "lesson-revisions.json"
    )
    second = LessonRevisionHistoryStore(
        tmp_path / "vaults" / "vault-b" / "lesson-revisions.json"
    )

    item = revision("python/example", 0, "A", action="baseline")
    first.append(item)

    assert first.list("python/example") == (item,)
    assert second.list("python/example") == ()


def test_store_refuses_to_write_state_larger_than_its_read_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "lesson-revisions.json"
    store = LessonRevisionHistoryStore(path)

    monkeypatch.setattr(revision_history, "MAX_HISTORY_BYTES", 200)

    with pytest.raises(LessonRevisionHistoryError, match="exceeds size limits"):
        store.append(
            revision(
                "python/example",
                0,
                "x" * 256,
                action="baseline",
            )
        )

    assert not path.exists()


def test_snapshot_limit_matches_canonical_markdown_member_limit() -> None:
    assert revision_history.MAX_SNAPSHOT_BYTES == 32 * 1024 * 1024


def _write_revision_fixture(vault: Path) -> Path:
    return write_lesson_markdown(
        vault,
        lesson_id="python/example",
        body="Before",
        topic="python",
        source="note",
        importance=3,
        tags=["python"],
        date="2026-08-15",
        title="Example",
    )


def _revisioned_edit(
    vault: Path,
    store: LessonRevisionHistoryStore,
    expected: str,
    *,
    body: str,
):
    return write_revisioned_canonical_lesson_source(
        vault_dir=vault,
        lesson_id="python/example",
        expected_revision=expected,
        history_store=store,
        body=body,
        topic="python",
        source="note",
        importance=3,
        tags=["python"],
        date="2026-08-15",
        title="Example",
        lifecycle="active",
        superseded_by=None,
        invalidate_cache=lambda: None,
        occurred_at="2026-08-15T15:00:00+00:00",
    )


def test_first_revisioned_edit_records_baseline_and_edit(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_revision_fixture(vault)
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    state = read_canonical_lesson_revision(
        vault_dir=vault,
        lesson_id="python/example",
    )
    result = _revisioned_edit(vault, store, state.canonical_revision, body="After")

    revisions = store.list("python/example")
    assert result.canonical_changed is True
    assert result.revision == 1
    assert [item.action for item in revisions] == ["baseline", "edit"]
    assert revisions[0].canonical_fingerprint == state.canonical_revision
    assert revisions[1].canonical_fingerprint == result.canonical_revision
    assert revisions[0].markdown != revisions[1].markdown


def test_revisioned_identical_write_is_a_history_noop(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_revision_fixture(vault)
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    state = read_canonical_lesson_revision(
        vault_dir=vault,
        lesson_id="python/example",
    )
    result = _revisioned_edit(
        vault,
        store,
        state.canonical_revision,
        body="Before",
    )

    assert result.canonical_changed is False
    assert result.revision is None
    assert store.list("python/example") == ()


def test_revisioned_edit_rejects_external_stale_change_without_history_mutation(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    path = _write_revision_fixture(vault)
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    stale = read_canonical_lesson_revision(
        vault_dir=vault,
        lesson_id="python/example",
    ).canonical_revision

    path.write_text(
        path.read_text(encoding="utf-8").replace("Before", "External"),
        encoding="utf-8",
    )
    before = path.read_bytes()

    with pytest.raises(CanonicalLessonWriteStaleError):
        _revisioned_edit(vault, store, stale, body="Managed")

    assert path.read_bytes() == before
    assert store.list("python/example") == ()


def test_revisioned_edit_fails_closed_when_existing_history_diverged(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    path = _write_revision_fixture(vault)
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    initial = read_canonical_lesson_revision(
        vault_dir=vault,
        lesson_id="python/example",
    ).canonical_revision
    _revisioned_edit(vault, store, initial, body="Managed")

    path.write_text(
        path.read_text(encoding="utf-8").replace("Managed", "External"),
        encoding="utf-8",
    )
    current = read_canonical_lesson_revision(
        vault_dir=vault,
        lesson_id="python/example",
    ).canonical_revision
    history_before = store.list("python/example")

    with pytest.raises(CanonicalLessonWriteHistoryError, match="diverged"):
        _revisioned_edit(vault, store, current, body="Another")

    assert store.list("python/example") == history_before


def test_revision_diff_is_derived_from_snapshots(tmp_path: Path) -> None:
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")
    store.append(revision("python/example", 0, "before\n", action="baseline"))
    store.append(revision("python/example", 1, "after\n", action="edit"))

    diff = diff_lesson_revisions(
        history_store=store,
        lesson_id="python/example",
        from_revision=0,
        to_revision=1,
    )

    assert "--- revision-0.md" in diff
    assert "+++ revision-1.md" in diff
    assert "-before" in diff
    assert "+after" in diff


def test_rollback_appends_new_revision_without_erasing_history(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    _write_revision_fixture(vault)
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    initial = read_canonical_lesson_revision(
        vault_dir=vault,
        lesson_id="python/example",
    ).canonical_revision
    edited = _revisioned_edit(vault, store, initial, body="After")

    result = rollback_canonical_lesson_source(
        vault_dir=vault,
        lesson_id="python/example",
        target_revision=0,
        expected_revision=edited.canonical_revision,
        history_store=store,
        invalidate_cache=lambda: None,
        occurred_at="2026-08-15T16:00:00+00:00",
        reason="restore baseline",
    )

    revisions = store.list("python/example")
    assert [item.revision for item in revisions] == [0, 1, 2]
    assert [item.action for item in revisions] == [
        "baseline",
        "edit",
        "rollback",
    ]
    assert revisions[2].rollback_from_revision == 0
    assert revisions[2].canonical_fingerprint == revisions[0].canonical_fingerprint
    assert "Before" in result.path.read_text(encoding="utf-8")
    assert result.canonical_revision == revisions[0].canonical_fingerprint


def test_rollback_rejects_stale_current_state_without_mutation(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    path = _write_revision_fixture(vault)
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    initial = read_canonical_lesson_revision(
        vault_dir=vault,
        lesson_id="python/example",
    ).canonical_revision
    edited = _revisioned_edit(vault, store, initial, body="After")

    before_history = store.list("python/example")
    path.write_text(
        path.read_text(encoding="utf-8").replace("After", "External"),
        encoding="utf-8",
    )
    before_file = path.read_bytes()

    with pytest.raises(CanonicalLessonWriteStaleError):
        rollback_canonical_lesson_source(
            vault_dir=vault,
            lesson_id="python/example",
            target_revision=0,
            expected_revision=edited.canonical_revision,
            history_store=store,
            invalidate_cache=lambda: None,
        )

    assert path.read_bytes() == before_file
    assert store.list("python/example") == before_history
