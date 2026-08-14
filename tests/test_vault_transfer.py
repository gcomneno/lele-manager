from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server as server_mod
from lele_manager.api.server import app
from lele_manager.core import vault_transfer
from lele_manager.core.duplicate_decisions import material_fingerprint
from lele_manager.core.vault import write_lesson_markdown
from lele_manager.core.vault_registry import ActiveVaultContext, VaultRegistryStore
from lele_manager.core.vault_snapshot import SnapshotTargetError
from lele_manager.core.vault_transfer import (
    VaultTransferConflictError,
    VaultTransferPlanStaleError,
    execute_transfer,
    preview_transfer,
)


A_ID = "11111111-1111-1111-1111-111111111111"
B_ID = "22222222-2222-2222-2222-222222222222"
C_ID = "33333333-3333-3333-3333-333333333333"


def _context(tmp_path: Path, vault_id: str, name: str) -> ActiveVaultContext:
    root = tmp_path / name.lower()
    root.mkdir(parents=True)
    return ActiveVaultContext(
        vault_id,
        name,
        root,
        tmp_path / "data" / "vaults" / vault_id / "lessons.jsonl",
        tmp_path / "data" / "vaults" / vault_id / "candidates.json",
        tmp_path / "cache" / "vaults" / vault_id / "topic_model.joblib",
        vault_id,
    )


def _write(
    context: ActiveVaultContext,
    lesson_id: str,
    body: str,
    *,
    relative_path: str | None = None,
    title: str = "Transfer test",
) -> Path:
    return write_lesson_markdown(
        context.vault_dir,
        lesson_id=lesson_id,
        body=body,
        topic="transfer",
        source="test",
        importance=3,
        tags=["transfer"],
        date="2026-08-12",
        title=title,
        relative_path=relative_path,
    )


def _preview(
    source: ActiveVaultContext,
    destination: ActiveVaultContext,
    lesson_id: str,
    *,
    operation: str = "merge",
    resolution: str | None = None,
):
    return preview_transfer(
        operation=operation,  # type: ignore[arg-type]
        source=source,
        destination=destination,
        selections=((lesson_id, resolution),),  # type: ignore[arg-type]
    )


def _execute(
    preview,
    source: ActiveVaultContext,
    destination: ActiveVaultContext,
    lesson_id: str,
    *,
    operation: str = "merge",
    resolution: str | None = None,
    reconcile_destination=lambda _context: None,
    reconcile_source=lambda _context: None,
):
    return execute_transfer(
        operation=operation,  # type: ignore[arg-type]
        source=source,
        destination=destination,
        selections=((lesson_id, resolution),),  # type: ignore[arg-type]
        plan_digest=preview.plan_digest,
        resolve_source=lambda: source,
        resolve_destination=lambda: destination,
        reconcile_destination=reconcile_destination,
        reconcile_source=reconcile_source,
    )


def test_preview_classification_contract_and_purity(tmp_path: Path) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    new = _write(source, "transfer/new", "new body", relative_path="transfer/new.md")
    identical = _write(source, "transfer/identical", "same bytes", relative_path="transfer/identical.md")
    (destination.vault_dir / "transfer").mkdir()
    (destination.vault_dir / "transfer" / "identical.md").write_bytes(identical.read_bytes())
    present = _write(source, "transfer/present", "present bytes", relative_path="transfer/present-source.md")
    (destination.vault_dir / "elsewhere").mkdir()
    (destination.vault_dir / "elsewhere" / "present.md").write_bytes(present.read_bytes())
    same_id = _write(source, "transfer/same-id", "semantic body", relative_path="transfer/same-id.md")
    destination_same_id = destination.vault_dir / "elsewhere" / "same-id.md"
    destination_same_id.write_bytes(same_id.read_bytes() + b"\n")
    path_conflict = _write(source, "transfer/path-source", "path source", relative_path="transfer/occupied.md")
    _write(destination, "transfer/path-other", "path other", relative_path="transfer/occupied.md")
    duplicate = _write(source, "transfer/duplicate-source", "identical duplicate body", relative_path="transfer/duplicate-source.md")
    _write(destination, "transfer/duplicate-destination", "identical duplicate body", relative_path="transfer/duplicate-destination.md")

    before_source = {path.relative_to(source.vault_dir): path.read_bytes() for path in source.vault_dir.rglob("*.md")}
    before_destination = {path.relative_to(destination.vault_dir): path.read_bytes() for path in destination.vault_dir.rglob("*.md")}
    assert not source.projection_path.exists() and not destination.projection_path.exists()
    assert not source.topic_model_path.exists() and not destination.topic_model_path.exists()

    selections = tuple((lesson_id, None) for lesson_id in (
        "transfer/new",
        "transfer/identical",
        "transfer/present",
        "transfer/same-id",
        "transfer/path-source",
        "transfer/duplicate-source",
    ))
    preview = preview_transfer(operation="merge", source=source, destination=destination, selections=selections)
    classes = {item.lesson_id: item.classification for item in preview.items}
    assert classes == {
        "transfer/duplicate-source": "likely_duplicate",
        "transfer/identical": "identical",
        "transfer/new": "new",
        "transfer/path-source": "path_conflict",
        "transfer/present": "already_present",
        "transfer/same-id": "same_id",
    }
    present_preview = next(item for item in preview.items if item.lesson_id == "transfer/present")
    assert present_preview.destination_path == "elsewhere/present.md"
    same_id_preview = next(item for item in preview.items if item.lesson_id == "transfer/same-id")
    assert same_id_preview.destination_path == "elsewhere/same-id.md"

    source_record = vault_transfer._lessons(source)["transfer/same-id"]
    destination_record = vault_transfer._lessons(destination)["transfer/same-id"]
    assert source_record.raw != destination_record.raw
    assert material_fingerprint(source_record.record) == material_fingerprint(destination_record.record)

    assert {path.relative_to(source.vault_dir): path.read_bytes() for path in source.vault_dir.rglob("*.md")} == before_source
    assert {path.relative_to(destination.vault_dir): path.read_bytes() for path in destination.vault_dir.rglob("*.md")} == before_destination
    assert not source.projection_path.exists() and not destination.projection_path.exists()
    assert not source.topic_model_path.exists() and not destination.topic_model_path.exists()
    assert new.exists() and path_conflict.exists() and duplicate.exists()


def test_merge_copy_noop_and_isolation_semantics(tmp_path: Path) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    third = _context(tmp_path, C_ID, "C")
    source_path = _write(source, "transfer/new", "new body")
    third_path = _write(third, "transfer/c", "C remains")
    third_before = third_path.read_bytes()
    destination_refreshes = 0
    source_refreshes = 0

    preview = _preview(source, destination, "transfer/new")
    result = _execute(
        preview,
        source,
        destination,
        "transfer/new",
        reconcile_destination=lambda _context: globals(),
    )
    assert result.items[0].outcome == "destination_written"
    assert source_path.exists()
    assert (destination.vault_dir / "transfer" / "new.md").read_bytes() == source_path.read_bytes()
    assert third_path.read_bytes() == third_before

    exact_preview = _preview(source, destination, "transfer/new")
    assert exact_preview.items[0].classification == "identical"

    def destination_refresh(_context: ActiveVaultContext) -> None:
        nonlocal destination_refreshes
        destination_refreshes += 1

    def source_refresh(_context: ActiveVaultContext) -> None:
        nonlocal source_refreshes
        source_refreshes += 1

    exact_result = _execute(
        exact_preview,
        source,
        destination,
        "transfer/new",
        reconcile_destination=destination_refresh,
        reconcile_source=source_refresh,
    )
    assert exact_result.items[0].outcome == "destination_already_exact"
    assert exact_result.items[0].destination_derived == "not_needed"
    assert exact_result.destination_derived_reconciled is None
    assert destination_refreshes == 0 and source_refreshes == 0
    assert source_path.exists()

    copy_source = _write(source, "transfer/copy", "copy body")
    copy_preview = _preview(source, destination, "transfer/copy", operation="copy")
    _execute(copy_preview, source, destination, "transfer/copy", operation="copy")
    assert copy_source.exists()


def test_explicit_conflict_resolution_requires_fresh_preview(tmp_path: Path) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    _write(source, "transfer/conflict", "source")
    destination_path = _write(destination, "transfer/conflict", "destination")
    before = destination_path.read_bytes()
    unresolved = _preview(source, destination, "transfer/conflict")
    assert unresolved.items[0].classification == "same_id"
    assert unresolved.items[0].resolution is None
    with pytest.raises(VaultTransferConflictError):
        _execute(unresolved, source, destination, "transfer/conflict")
    with pytest.raises(VaultTransferPlanStaleError):
        _execute(unresolved, source, destination, "transfer/conflict", resolution="keep_destination")

    resolved = _preview(source, destination, "transfer/conflict", resolution="keep_destination")
    result = _execute(resolved, source, destination, "transfer/conflict", resolution="keep_destination")
    assert result.items[0].outcome == "skipped_by_resolution"
    assert destination_path.read_bytes() == before


def test_stale_source_destination_selection_and_resolution_are_rejected(tmp_path: Path) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    first = _write(source, "transfer/first", "first")
    _write(source, "transfer/second", "second")
    preview = _preview(source, destination, "transfer/first")
    first.write_bytes(first.read_bytes() + b"changed")
    with pytest.raises(VaultTransferPlanStaleError):
        _execute(preview, source, destination, "transfer/first")

    first.write_bytes(first.read_bytes().removesuffix(b"changed"))
    preview = _preview(source, destination, "transfer/first")
    _write(destination, "transfer/other", "destination changed")
    with pytest.raises(VaultTransferPlanStaleError):
        _execute(preview, source, destination, "transfer/first")

    clean_destination = _context(tmp_path, C_ID, "C")
    preview = _preview(source, clean_destination, "transfer/first")
    with pytest.raises(VaultTransferPlanStaleError):
        execute_transfer(
            operation="merge",
            source=source,
            destination=clean_destination,
            selections=(("transfer/second", None),),
            plan_digest=preview.plan_digest,
            resolve_source=lambda: source,
            resolve_destination=lambda: clean_destination,
            reconcile_destination=lambda _context: None,
            reconcile_source=lambda _context: None,
        )


def test_execute_rejects_state_changed_during_context_resolution(tmp_path: Path) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    source_path = _write(source, "transfer/window", "previewed bytes")
    preview = _preview(source, destination, "transfer/window")
    changed = source_path.read_bytes() + b"changed after recomputation"

    def resolve_changed_source() -> ActiveVaultContext:
        source_path.write_bytes(changed)
        return source

    with pytest.raises(VaultTransferPlanStaleError):
        execute_transfer(
            operation="merge",
            source=source,
            destination=destination,
            selections=(("transfer/window", None),),
            plan_digest=preview.plan_digest,
            resolve_source=resolve_changed_source,
            resolve_destination=lambda: destination,
            reconcile_destination=lambda _context: None,
            reconcile_source=lambda _context: None,
        )

    assert source_path.read_bytes() == changed
    assert not (destination.vault_dir / "transfer" / "window.md").exists()


def test_likely_duplicate_keeps_exact_semantics_when_features_cannot_fit(
    tmp_path: Path,
) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    _write(source, "transfer/short-source", "x")
    _write(destination, "transfer/short-destination", "x")

    preview = _preview(source, destination, "transfer/short-source")

    assert preview.items[0].classification == "likely_duplicate"
    assert preview.items[0].duplicate_lesson_ids == (
        "transfer/short-destination",
    )


def test_move_destination_first_partial_failure_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    source_path = _write(source, "transfer/move", "move body")
    source_refreshes = 0

    def fail_destination_derived(_context: ActiveVaultContext) -> None:
        raise RuntimeError("derived unavailable")

    def source_refresh(_context: ActiveVaultContext) -> None:
        nonlocal source_refreshes
        source_refreshes += 1

    preview = _preview(source, destination, "transfer/move", operation="move")
    result = _execute(
        preview,
        source,
        destination,
        "transfer/move",
        operation="move",
        reconcile_destination=fail_destination_derived,
        reconcile_source=source_refresh,
    )
    destination_path = destination.vault_dir / "transfer" / "move.md"
    assert destination_path.exists()
    assert not source_path.exists()
    assert result.destination_derived_reconciled is False
    assert result.items[0].destination_canonical == "written"
    assert result.items[0].source_canonical == "deleted"
    assert source_refreshes == 1

    second_source = _write(source, "transfer/delete-fails", "delete failure")
    second_preview = _preview(source, destination, "transfer/delete-fails", operation="move")
    original_delete = vault_transfer.delete_canonical_file

    def fail_delete(*_args: object, **_kwargs: object) -> None:
        raise SnapshotTargetError("injected delete failure")

    monkeypatch.setattr(vault_transfer, "delete_canonical_file", fail_delete)
    result = _execute(second_preview, source, destination, "transfer/delete-fails", operation="move")
    assert result.items[0].outcome == "move_source_delete_failed"
    assert second_source.exists()
    assert (destination.vault_dir / "transfer" / "delete-fails.md").exists()
    assert result.source_derived_reconciled is None
    monkeypatch.setattr(vault_transfer, "delete_canonical_file", original_delete)


def test_move_exact_existing_and_destination_failure_leave_correct_source_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    source_path = _write(source, "transfer/exact", "exact", relative_path="transfer/source-exact.md")
    (destination.vault_dir / "elsewhere").mkdir()
    existing = destination.vault_dir / "elsewhere" / "exact.md"
    existing.write_bytes(source_path.read_bytes())
    destination_refreshes = 0

    def destination_refresh(_context: ActiveVaultContext) -> None:
        nonlocal destination_refreshes
        destination_refreshes += 1

    preview = _preview(source, destination, "transfer/exact", operation="move")
    assert preview.items[0].classification == "already_present"
    result = _execute(
        preview,
        source,
        destination,
        "transfer/exact",
        operation="move",
        reconcile_destination=destination_refresh,
    )
    assert result.items[0].outcome == "moved"
    assert result.items[0].destination_canonical == "already_exact"
    assert not source_path.exists()
    assert existing.exists()
    assert destination_refreshes == 0

    failed_source = _write(source, "transfer/write-fails", "write fails")
    failed_preview = _preview(source, destination, "transfer/write-fails", operation="move")

    def fail_write(*_args: object, **_kwargs: object) -> Path:
        raise SnapshotTargetError("injected destination failure")

    monkeypatch.setattr(vault_transfer, "write_new_canonical_file", fail_write)
    failed = _execute(failed_preview, source, destination, "transfer/write-fails", operation="move")
    assert failed.items[0].outcome == "destination_write_failed"
    assert failed_source.exists()


def test_late_destination_collision_never_overwrites_and_unsafe_links_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    source_path = _write(source, "transfer/late", "late")
    preview = _preview(source, destination, "transfer/late", operation="move")
    original_write = vault_transfer.write_new_canonical_file

    def collide(root: Path, relative_path: str, data: bytes) -> Path:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"late collision")
        return original_write(root, relative_path, data)

    monkeypatch.setattr(vault_transfer, "write_new_canonical_file", collide)
    result = _execute(preview, source, destination, "transfer/late", operation="move")
    assert result.items[0].outcome == "destination_write_failed"
    assert source_path.exists()
    assert (destination.vault_dir / "transfer" / "late.md").read_bytes() == b"late collision"

    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    unsafe_source = _context(tmp_path / "unsafe-source", "44444444-4444-4444-4444-444444444444", "Source")
    unsafe_destination = _context(tmp_path / "unsafe-destination", "55555555-5555-5555-5555-555555555555", "Destination")
    _write(unsafe_source, "transfer/unsafe", "unsafe")
    (unsafe_source.vault_dir / "link.md").symlink_to(outside)
    with pytest.raises(SnapshotTargetError):
        _preview(unsafe_source, unsafe_destination, "transfer/unsafe")

    (unsafe_source.vault_dir / "link.md").unlink()
    (unsafe_destination.vault_dir / "link.md").symlink_to(outside)
    with pytest.raises(SnapshotTargetError):
        _preview(unsafe_source, unsafe_destination, "transfer/unsafe")


def test_transfer_api_requires_registered_distinct_vaults_and_keeps_active_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_a = tmp_path / "vault-a"
    vault_b = tmp_path / "vault-b"
    vault_c = tmp_path / "vault-c"
    vault_a.mkdir()
    vault_b.mkdir()
    vault_c.mkdir()
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault_a))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(server_mod, "DATA_PATH", None)
    monkeypatch.setattr(server_mod, "MODEL_PATH", None)
    monkeypatch.setattr(server_mod, "DUPLICATE_DECISIONS_PATH", None)
    store = VaultRegistryStore()
    active = store.bootstrap()
    registered_b = store.register("Vault B", vault_b)
    registered_c = store.register("Vault C", vault_c)
    source_context = store.safe_context_for_registered(active.id)
    _write(source_context, "transfer/api", "api body")
    c_marker = vault_c / "marker.txt"
    c_marker.write_text("untouched", encoding="utf-8")
    registry_before = store.path.read_bytes()
    client = TestClient(app)

    missing = client.post("/vault-transfers/preview", json={
        "source_vault_id": active.id,
        "destination_vault_id": "99999999-9999-9999-9999-999999999999",
        "operation": "merge",
        "selections": [{"lesson_id": "transfer/api"}],
    })
    assert missing.status_code == 404
    same = client.post("/vault-transfers/preview", json={
        "source_vault_id": active.id,
        "destination_vault_id": active.id,
        "operation": "merge",
        "selections": [{"lesson_id": "transfer/api"}],
    })
    assert same.status_code == 422

    preview_response = client.post("/vault-transfers/preview", json={
        "source_vault_id": active.id,
        "destination_vault_id": registered_b.id,
        "operation": "merge",
        "selections": [{"lesson_id": "transfer/api"}],
    })
    assert preview_response.status_code == 200, preview_response.text
    assert store.active().id == active.id
    assert not (tmp_path / "data" / "vaults" / registered_b.id / "lessons.jsonl").exists()
    assert not (tmp_path / "cache" / "vaults" / registered_b.id / "topic_model.joblib").exists()

    execution = client.post("/vault-transfers/execute", json={
        "source_vault_id": active.id,
        "destination_vault_id": registered_b.id,
        "operation": "merge",
        "selections": [{"lesson_id": "transfer/api"}],
        "plan_digest": preview_response.json()["plan_digest"],
    })
    assert execution.status_code == 200, execution.text
    assert execution.json()["items"][0]["outcome"] == "destination_written"
    assert store.active().id == active.id
    assert c_marker.read_text(encoding="utf-8") == "untouched"
    assert store.path.read_bytes() == registry_before
    assert registered_c.id != registered_b.id


def test_transfer_does_not_leak_candidates_or_duplicate_decisions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _context(tmp_path, A_ID, "A")
    destination = _context(tmp_path, B_ID, "B")
    _write(source, "transfer/state", "state")
    source.candidates_path.parent.mkdir(parents=True)
    source.candidates_path.write_bytes(b"source-candidates")
    destination.candidates_path.parent.mkdir(parents=True)
    destination.candidates_path.write_bytes(b"destination-candidates")
    decisions = tmp_path / "data" / "duplicate-decisions.json"
    decisions.write_bytes(b"decision-state")
    before = (source.candidates_path.read_bytes(), destination.candidates_path.read_bytes(), decisions.read_bytes())

    preview = _preview(source, destination, "transfer/state")
    _execute(preview, source, destination, "transfer/state")
    after = (source.candidates_path.read_bytes(), destination.candidates_path.read_bytes(), decisions.read_bytes())
    assert after == before
