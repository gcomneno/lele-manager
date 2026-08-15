from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import Event, RLock, Thread, current_thread
from typing import Iterator

import pytest

import lele_manager.core.vault_danger as danger_module
import lele_manager.core.vault_registry as vault_registry_module
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
from lele_manager.core.vault_registry import (
    ActiveVaultContext,
    VaultNotFoundError,
    VaultRegistryStore,
)


class _ObservedRLock:
    """RLock test double that reports one named contender's acquire attempt."""

    def __init__(self, contender_name: str) -> None:
        self._lock = RLock()
        self._contender_name = contender_name
        self.contender_attempted = Event()

    def __enter__(self) -> "_ObservedRLock":
        if current_thread().name == self._contender_name:
            self.contender_attempted.set()
        self._lock.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self._lock.release()


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


@contextmanager
def _noop_mutation_boundary() -> Iterator[None]:
    yield


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
    mutation_boundary=None,
):
    if mutation_boundary is None:
        mutation_boundary = _noop_mutation_boundary

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
        mutation_boundary=mutation_boundary,
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
            mutation_boundary=_noop_mutation_boundary,
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


def test_backup_race_stales_before_canonical_deletion(tmp_path: Path) -> None:
    target = _context(tmp_path, B_ID, "B")
    path = _write(target, "topic/one", "previewed")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="empty", target=target, active_vault_id=A_ID, decisions=decisions
    )

    def backup_then_change(_context: ActiveVaultContext) -> str:
        path.write_bytes(_lesson("topic/one", "changed during backup"))
        return "/backup.snapshot.zip"

    with pytest.raises(VaultDangerPlanStaleError):
        _execute(
            preview=preview,
            target=target,
            decisions=decisions,
            backup_before=True,
            create_backup=backup_then_change,
        )

    assert path.read_bytes() == _lesson("topic/one", "changed during backup")


def test_reset_preserves_editorial_state_changed_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _context(tmp_path, B_ID, "B")
    _write(target, "topic/one")
    target.candidates_path.parent.mkdir(parents=True)
    target.candidates_path.write_text("old")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="reset", target=target, active_vault_id=A_ID, decisions=decisions
    )
    original = danger_module._delete_canonical_set

    def delete_then_change(root: Path, canonical: dict[str, bytes]) -> tuple[int, str | None]:
        result = original(root, canonical)
        target.candidates_path.write_text("newer")
        return result

    monkeypatch.setattr(danger_module, "_delete_canonical_set", delete_then_change)
    result = _execute(preview=preview, target=target, decisions=decisions)

    assert result.canonical_complete is True
    assert result.editorial_cleared is False
    assert "newer state was preserved" in (result.editorial_error or "")
    assert target.candidates_path.read_text() == "newer"


def test_late_foreign_file_after_canonical_delete_is_truthful_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _context(tmp_path, B_ID, "B")
    _write(target, "topic/one")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="delete", target=target, active_vault_id=A_ID, decisions=decisions
    )
    original = danger_module._delete_canonical_set
    foreign = target.vault_dir / "arrived-late.txt"

    def delete_then_add_foreign(root: Path, canonical: dict[str, bytes]) -> tuple[int, str | None]:
        result = original(root, canonical)
        foreign.write_text("preserve me")
        return result

    monkeypatch.setattr(danger_module, "_delete_canonical_set", delete_then_add_foreign)
    result = _execute(preview=preview, target=target, decisions=decisions)

    assert result.canonical_complete is True
    assert result.vault_directory_deleted is False
    assert "non-Markdown file" in (result.vault_directory_error or "")
    assert result.registry_removed is None
    assert foreign.read_text() == "preserve me"


def test_delete_holds_mutation_boundary_through_authority_and_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _context(tmp_path, B_ID, "B")
    _write(target, "topic/one")
    decisions = _decisions(tmp_path)
    preview = preview_vault_danger(
        operation="delete",
        target=target,
        active_vault_id=A_ID,
        decisions=decisions,
    )

    boundary_held = False
    authority_checked_inside = False
    canonical_deleted_inside = False
    registry_removed_inside = False

    @contextmanager
    def mutation_boundary() -> Iterator[None]:
        nonlocal boundary_held
        assert boundary_held is False
        boundary_held = True
        try:
            yield
        finally:
            boundary_held = False

    original_delete = danger_module._delete_canonical_set

    def delete_inside_boundary(
        root: Path, canonical: dict[str, bytes]
    ) -> tuple[int, str | None]:
        nonlocal canonical_deleted_inside
        canonical_deleted_inside = boundary_held
        return original_delete(root, canonical)

    def resolve_active() -> str:
        nonlocal authority_checked_inside
        if boundary_held:
            authority_checked_inside = True
        return A_ID

    def remove_registry(_context: ActiveVaultContext) -> None:
        nonlocal registry_removed_inside
        registry_removed_inside = boundary_held

    monkeypatch.setattr(
        danger_module,
        "_delete_canonical_set",
        delete_inside_boundary,
    )

    result = execute_vault_danger(
        operation=preview.operation,
        target=target,
        active_vault_id=A_ID,
        decisions=decisions,
        plan_digest=preview.plan_digest,
        confirmation=preview.confirmation_text,
        backup_before=False,
        resolve_target=lambda: target,
        resolve_active_vault_id=resolve_active,
        reconcile_derived=lambda _context: None,
        invalidate_cache=lambda _context: None,
        remove_registry=remove_registry,
        create_backup=lambda _context: "/backup.snapshot.zip",
        mutation_boundary=mutation_boundary,
    )

    assert result.vault_directory_deleted is True
    assert authority_checked_inside is True
    assert canonical_deleted_inside is True
    assert registry_removed_inside is True
    assert boundary_held is False


def test_concurrent_activation_cannot_enter_vault_during_physical_delete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vault_a = tmp_path / "vault-a"
    vault_b = tmp_path / "vault-b"
    vault_a.mkdir()
    vault_b.mkdir()

    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault_a))

    store = VaultRegistryStore()
    active_a = store.bootstrap()
    registered_b = store.register("B", vault_b)
    target = store.safe_context_for_registered(registered_b.id)
    _write(target, "topic/one")
    decisions = _decisions(tmp_path)

    preview = preview_vault_danger(
        operation="delete",
        target=target,
        active_vault_id=active_a.id,
        decisions=decisions,
    )

    commit_entered = Event()
    allow_delete = Event()
    activation_finished = Event()

    observed_lock = _ObservedRLock("danger-activation-contender")
    monkeypatch.setattr(vault_registry_module, "_LOCK", observed_lock)

    delete_result: list[object] = []
    delete_errors: list[BaseException] = []
    activation_errors: list[BaseException] = []

    original_delete = danger_module._delete_canonical_set

    def blocked_delete(
        root: Path, canonical: dict[str, bytes]
    ) -> tuple[int, str | None]:
        commit_entered.set()
        if not allow_delete.wait(timeout=2):
            raise AssertionError("test did not release destructive commit")
        return original_delete(root, canonical)

    def run_delete() -> None:
        try:
            delete_result.append(
                execute_vault_danger(
                    operation=preview.operation,
                    target=target,
                    active_vault_id=active_a.id,
                    decisions=decisions,
                    plan_digest=preview.plan_digest,
                    confirmation=preview.confirmation_text,
                    backup_before=False,
                    resolve_target=lambda: store.safe_context_for_registered(
                        registered_b.id
                    ),
                    resolve_active_vault_id=lambda: store.active().id,
                    reconcile_derived=lambda _context: None,
                    invalidate_cache=lambda _context: None,
                    remove_registry=lambda context: store.remove(context.vault_id),
                    create_backup=lambda _context: "/backup.snapshot.zip",
                    mutation_boundary=store.mutation_boundary,
                )
            )
        except BaseException as exc:
            delete_errors.append(exc)

    def run_activation() -> None:
        try:
            store.activate(registered_b.id)
        except BaseException as exc:
            activation_errors.append(exc)
        finally:
            activation_finished.set()

    monkeypatch.setattr(
        danger_module,
        "_delete_canonical_set",
        blocked_delete,
    )

    delete_thread = Thread(target=run_delete, daemon=True)
    delete_thread.start()
    assert commit_entered.wait(timeout=2)

    activation_thread = Thread(
        target=run_activation,
        daemon=True,
        name="danger-activation-contender",
    )
    activation_thread.start()

    # The lock itself reports the contender's acquire attempt. The delete
    # thread still owns that same RLock, so activation cannot complete.
    assert observed_lock.contender_attempted.wait(timeout=2)
    assert activation_finished.is_set() is False

    allow_delete.set()

    delete_thread.join(timeout=2)
    activation_thread.join(timeout=2)

    assert not delete_thread.is_alive()
    assert not activation_thread.is_alive()
    assert delete_errors == []
    assert len(delete_result) == 1

    result = delete_result[0]
    assert result.vault_directory_deleted is True
    assert result.registry_removed is True
    assert not vault_b.exists()

    assert len(activation_errors) == 1
    assert isinstance(activation_errors[0], VaultNotFoundError)
    assert store.active().id == active_a.id
