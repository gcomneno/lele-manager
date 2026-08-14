from __future__ import annotations

from pathlib import Path

import pytest

from lele_manager.core.duplicate_decisions import DuplicateDecisionStore
from lele_manager.core.vault_danger import (
    VaultDangerBackupError,
    VaultDangerConfirmationError,
    VaultDangerMergeVerificationError,
    VaultDangerPlanStaleError,
    VaultDangerTargetError,
    execute_vault_danger,
    preview_vault_danger,
)
from lele_manager.core.vault_registry import ActiveVaultContext


A_ID = "11111111-1111-4111-8111-111111111111"
B_ID = "22222222-2222-4222-8222-222222222222"
C_ID = "33333333-3333-4333-8333-333333333333"


def _context(tmp_path: Path, vault_id: str, name: str) -> ActiveVaultContext:
    vault_dir = tmp_path / "vaults" / name
    vault_dir.mkdir(parents=True)
    return ActiveVaultContext(
        vault_id=vault_id,
        display_name=name,
        vault_dir=vault_dir,
        projection_path=tmp_path / "data" / "vaults" / vault_id / "lessons.jsonl",
        candidates_path=tmp_path / "data" / "vaults" / vault_id / "candidates.json",
        topic_model_path=tmp_path / "cache" / "vaults" / vault_id / "topic_model.joblib",
        duplicate_decision_scope=vault_id,
    )


def _lesson(lesson_id: str, body: str = "body") -> bytes:
    return (
        "---\n"
        f"id: {lesson_id}\n"
        "topic: danger\n"
        "source: test\n"
        "importance: 3\n"
        "tags: [danger]\n"
        "date: '2026-08-14'\n"
        f"title: {lesson_id}\n"
        "---\n"
        f"{body}\n"
    ).encode()


def _write(context: ActiveVaultContext, lesson_id: str, body: str = "body") -> Path:
    path = context.vault_dir / f"{lesson_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_lesson(lesson_id, body))
    return path


def _decisions(tmp_path: Path) -> DuplicateDecisionStore:
    return DuplicateDecisionStore(tmp_path / "data" / "duplicate-decisions.json")


def _execute(
    *,
    preview,
    target: ActiveVaultContext,
    decisions: DuplicateDecisionStore,
    active_id: str = A_ID,
    destination: ActiveVaultContext | None = None,
    backup_before: bool = False,
    create_backup=lambda _context: "/backup.snapshot.zip",
    reconcile=lambda _context: None,
    invalidate=lambda _context: None,
    remove_registry=lambda _context: None,
):
    return execute_vault_danger(
        operation=preview.operation,
        target=target,
        active_vault_id=active_id,
        decisions=decisions,
        plan_digest=preview.plan_digest,
        confirmation=preview.confirmation_text,
        backup_before=backup_before,
        destination=destination,
        resolve_target=lambda: target,
        resolve_active_vault_id=lambda: active_id,
        resolve_destination=(lambda: destination) if destination is not None else None,
        reconcile_derived=reconcile,
        invalidate_cache=invalidate,
        remove_registry=remove_registry,
        create_backup=create_backup,
    )


def test_reset_preview_is_side_effect_free(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    _write(target, "topic/one")
    decisions = _decisions(tmp_path)
    assert not target.candidates_path.parent.exists()
    assert not decisions.path.exists()

    preview = preview_vault_danger(
        operation="reset",
        target=target,
        active_vault_id=A_ID,
        decisions=decisions,
    )

    assert preview.approved_count == 1
    assert preview.confirmation_text == "RESET B"
    assert not target.candidates_path.parent.exists()
    assert not decisions.path.exists()


def test_wrong_confirmation_never_starts_destruction(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    path = _write(target, "topic/one")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="empty", target=target, active_vault_id=A_ID, decisions=decisions
    )

    with pytest.raises(VaultDangerConfirmationError):
        execute_vault_danger(
            operation="empty",
            target=target,
            active_vault_id=A_ID,
            decisions=decisions,
            plan_digest=preview.plan_digest,
            confirmation="EMPTY something-else",
            backup_before=False,
            resolve_target=lambda: target,
            resolve_active_vault_id=lambda: A_ID,
            reconcile_derived=lambda _context: None,
            invalidate_cache=lambda _context: None,
            remove_registry=lambda _context: None,
            create_backup=lambda _context: pytest.fail("backup must not run"),
        )

    assert path.exists()


def test_canonical_change_after_preview_is_stale(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    path = _write(target, "topic/one")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="empty", target=target, active_vault_id=A_ID, decisions=decisions
    )
    path.write_bytes(_lesson("topic/one", "changed"))

    with pytest.raises(VaultDangerPlanStaleError):
        _execute(preview=preview, target=target, decisions=decisions)

    assert path.read_bytes() == _lesson("topic/one", "changed")


def test_requested_backup_failure_blocks_deletion(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    path = _write(target, "topic/one")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="empty", target=target, active_vault_id=A_ID, decisions=decisions
    )

    def fail_backup(_context: ActiveVaultContext) -> str:
        raise OSError("disk full")

    with pytest.raises(VaultDangerBackupError):
        _execute(
            preview=preview,
            target=target,
            decisions=decisions,
            backup_before=True,
            create_backup=fail_backup,
        )

    assert path.exists()


def test_empty_reports_canonical_success_and_derived_failure(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    _write(target, "topic/one")
    target.candidates_path.parent.mkdir(parents=True)
    target.candidates_path.write_text("candidate state")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="empty", target=target, active_vault_id=A_ID, decisions=decisions
    )

    def fail_refresh(_context: ActiveVaultContext) -> None:
        raise RuntimeError("refresh failed")

    result = _execute(
        preview=preview,
        target=target,
        decisions=decisions,
        reconcile=fail_refresh,
    )

    assert result.canonical_deleted == 1
    assert result.canonical_complete is True
    assert result.derived_cleared is False
    assert result.partial is True
    assert target.vault_dir.is_dir()
    assert target.candidates_path.read_text() == "candidate state"


def test_reset_clears_only_target_scoped_editorial_and_derived_state(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    other = _context(tmp_path, C_ID, "C")
    _write(target, "topic/one")
    other_path = _write(other, "topic/other")
    target.candidates_path.parent.mkdir(parents=True)
    target.candidates_path.write_text("[]")
    target.projection_path.write_text("projection")
    target.topic_model_path.parent.mkdir(parents=True)
    target.topic_model_path.write_bytes(b"model")
    decisions = _decisions(tmp_path)
    decisions.save_not_duplicates(
        scope=B_ID,
        left_id="a",
        left_fingerprint="fa",
        right_id="b",
        right_fingerprint="fb",
    )
    decisions.save_not_duplicates(
        scope=C_ID,
        left_id="c",
        left_fingerprint="fc",
        right_id="d",
        right_fingerprint="fd",
    )
    preview = preview_vault_danger(
        operation="reset", target=target, active_vault_id=A_ID, decisions=decisions
    )

    result = _execute(preview=preview, target=target, decisions=decisions)

    assert result.canonical_complete is True
    assert result.editorial_cleared is True
    assert result.derived_cleared is True
    assert target.vault_dir.is_dir()
    assert not target.candidates_path.exists()
    assert not target.projection_path.exists()
    assert not target.topic_model_path.exists()
    assert decisions.export_scope(B_ID) == []
    assert len(decisions.export_scope(C_ID)) == 1
    assert other_path.exists()


def test_delete_refuses_foreign_regular_files_and_symlinks(tmp_path: Path) -> None:
    decisions = _decisions(tmp_path)
    foreign = _context(tmp_path, B_ID, "foreign")
    _write(foreign, "topic/one")
    (foreign.vault_dir / "notes.txt").write_text("not managed")
    with pytest.raises(VaultDangerTargetError):
        preview_vault_danger(
            operation="delete", target=foreign, active_vault_id=A_ID, decisions=decisions
        )

    linked = _context(tmp_path, C_ID, "linked")
    _write(linked, "topic/two")
    (linked.vault_dir / "link.md").symlink_to(linked.vault_dir / "topic" / "two.md")
    with pytest.raises(VaultDangerTargetError):
        preview_vault_danger(
            operation="delete", target=linked, active_vault_id=A_ID, decisions=decisions
        )


def test_merge_delete_requires_exact_stable_id_and_canonical_bytes(tmp_path: Path) -> None:
    source = _context(tmp_path, B_ID, "B")
    destination = _context(tmp_path, C_ID, "C")
    _write(source, "topic/one", "source")
    _write(destination, "topic/one", "different")
    decisions = _decisions(tmp_path)

    with pytest.raises(VaultDangerMergeVerificationError):
        preview_vault_danger(
            operation="merge_delete_source",
            target=source,
            destination=destination,
            active_vault_id=A_ID,
            decisions=decisions,
        )

    destination_file = destination.vault_dir / "topic" / "one.md"
    destination_file.write_bytes(_lesson("topic/one", "source"))
    preview = preview_vault_danger(
        operation="merge_delete_source",
        target=source,
        destination=destination,
        active_vault_id=A_ID,
        decisions=decisions,
    )
    assert preview.merge_verified is True

    destination_file.write_bytes(_lesson("topic/one", "changed after preview"))
    with pytest.raises(VaultDangerPlanStaleError):
        _execute(
            preview=preview,
            target=source,
            destination=destination,
            decisions=decisions,
        )
    assert source.vault_dir.is_dir()


def test_delete_removes_only_target_and_reports_registry_phase(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    other = _context(tmp_path, C_ID, "C")
    _write(target, "nested/one")
    other_path = _write(other, "nested/other")
    decisions = _decisions(tmp_path)
    removed: list[str] = []
    preview = preview_vault_danger(
        operation="delete", target=target, active_vault_id=A_ID, decisions=decisions
    )

    result = _execute(
        preview=preview,
        target=target,
        decisions=decisions,
        remove_registry=lambda context: removed.append(context.vault_id),
    )

    assert result.canonical_complete is True
    assert result.vault_directory_deleted is True
    assert result.vault_directory_error is None
    assert result.registry_removed is True
    assert removed == [B_ID]
    assert not target.vault_dir.exists()
    assert other_path.exists()
