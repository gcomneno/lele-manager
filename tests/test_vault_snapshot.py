from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lele_manager.api.server import app
from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.lesson_candidate import CandidateProvenance, LessonCandidate
from lele_manager.application.raw_source import SourceKind
from lele_manager.core.duplicate_decisions import DuplicateDecisionStore
from lele_manager.core.vault import write_lesson_markdown
from lele_manager.core.vault_registry import ActiveVaultContext
from lele_manager.core.vault_registry import VaultRegistryStore
from lele_manager.core.vault_snapshot import (
    SnapshotPlanStaleError,
    SnapshotRestoreError,
    SnapshotTargetError,
    SnapshotValidationError,
    create_snapshot,
    execute_restore,
    preview_restore,
    validate_snapshot,
)


SOURCE_ID = "11111111-1111-1111-1111-111111111111"
TARGET_ID = "22222222-2222-2222-2222-222222222222"


def _context(root: Path, vault_id: str, name: str) -> ActiveVaultContext:
    root.mkdir()
    return ActiveVaultContext(
        vault_id,
        name,
        root,
        root.parent / "data" / vault_id / "lessons.jsonl",
        root.parent / "data" / vault_id / "candidates.json",
        root.parent / "cache" / vault_id / "topic_model.joblib",
        vault_id,
    )


def _lesson(root: Path, lesson_id: str, body: str, *, relative_path: str | None = None) -> Path:
    return write_lesson_markdown(
        root,
        lesson_id=lesson_id,
        body=body,
        topic=lesson_id.split("/", 1)[0],
        source="test",
        importance=3,
        tags=["test"],
        date="2026-08-11",
        title="Snapshot test",
        relative_path=relative_path,
    )


def _with_manifest(raw: bytes, mutate: object) -> bytes:
    """Return an artifact whose manifest was changed without touching payloads."""
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, "w") as destination:
        manifest = json.loads(source.read("manifest.json"))
        mutate(manifest)
        for info in source.infolist():
            data = json.dumps(manifest).encode() if info.filename == "manifest.json" else source.read(info.filename)
            destination.writestr(info.filename, data)
    return output.getvalue()


def test_snapshot_round_trip_is_scoped_and_exact(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "data" / "duplicate-decisions.json")
    source_lesson = _lesson(source.vault_dir, "python/source", "source body")
    _lesson(target.vault_dir, "python/old", "old body")
    # The maintained Vault importer/tree treats every Markdown file beneath
    # the root as canonical input, even without frontmatter.
    (target.vault_dir / "notes.md").write_text("managed by the Vault contract", encoding="utf-8")
    (target.vault_dir / "unrelated.txt").write_text("keep", encoding="utf-8")
    decisions.save_not_duplicates(
        scope=source.vault_id,
        left_id="a",
        left_fingerprint="a-fingerprint",
        right_id="b",
        right_fingerprint="b-fingerprint",
    )
    decisions.save_not_duplicates(
        scope="other-vault",
        left_id="x",
        left_fingerprint="x-fingerprint",
        right_id="y",
        right_fingerprint="y-fingerprint",
    )
    candidate = LessonCandidate(
        text="candidate editorial state",
        provenance=CandidateProvenance(
            source_kind=SourceKind.IN_MEMORY,
            source_logical_name="snapshot-test",
            source_fingerprint="source-fingerprint",
            ingested_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        ),
    )
    JsonCandidateRepository(source.candidates_path).create(candidate)

    raw = create_snapshot(source, decisions)
    validated = validate_snapshot(raw)
    preview = preview_restore(validated, target, decisions)

    assert preview.target_vault_id == TARGET_ID
    assert preview.additions == ("python/source.md",)
    assert preview.removals == ("notes.md", "python/old.md")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert "canonical/python/source.md" in archive.namelist()
        assert "lessons.jsonl" not in " ".join(archive.namelist())
        assert "topic_model" not in " ".join(archive.namelist())
        assert str(source.vault_dir) not in archive.read("manifest.json").decode("utf-8")
        assert "other-vault" not in archive.read("editorial/duplicate-decisions.json").decode("utf-8")

    result = execute_restore(
        validated,
        target,
        decisions,
        plan_digest=preview.plan_digest,
        reconcile_derived=lambda: None,
    )

    assert result.canonical_restored and result.derived_reconciled
    assert (target.vault_dir / "python" / "source.md").read_bytes() == source_lesson.read_bytes()
    assert not (target.vault_dir / "python" / "old.md").exists()
    assert not (target.vault_dir / "notes.md").exists()
    assert (target.vault_dir / "unrelated.txt").read_text(encoding="utf-8") == "keep"
    assert decisions.export_scope(target.vault_id) == decisions.export_scope(source.vault_id)
    assert decisions.export_scope("other-vault")[0]["left_id"] == "x"
    assert JsonCandidateRepository(target.candidates_path).list()[0].candidate_id == candidate.candidate_id


def test_snapshot_validation_rejects_traversal_before_target_mutation(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    _lesson(source.vault_dir, "python/source", "source body")
    raw = create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(output, "w") as changed:
        for info in old.infolist():
            name = "canonical/../escape.md" if info.filename == "canonical/python/source.md" else info.filename
            changed.writestr(name, old.read(info.filename))
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(output.getvalue())


def test_restore_rejects_stale_preview_without_mutating(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    _lesson(source.vault_dir, "python/source", "source body")
    original = _lesson(target.vault_dir, "python/current", "current body")
    validated = validate_snapshot(create_snapshot(source, decisions))
    preview = preview_restore(validated, target, decisions)
    original.write_text(original.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

    with pytest.raises(SnapshotPlanStaleError):
        execute_restore(validated, target, decisions, plan_digest=preview.plan_digest, reconcile_derived=lambda: None)
    assert "changed" in original.read_text(encoding="utf-8")


def test_restore_rolls_back_after_mid_apply_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    _lesson(source.vault_dir, "python/source", "source body")
    original = _lesson(target.vault_dir, "python/current", "current body")
    original_bytes = original.read_bytes()
    validated = validate_snapshot(create_snapshot(source, decisions))
    preview = preview_restore(validated, target, decisions)

    from lele_manager.core import vault_snapshot

    original_write = vault_snapshot._atomic_write
    calls = 0

    def fail_once(path: Path, data: bytes, **_: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected write failure")
        original_write(path, data)

    monkeypatch.setattr(vault_snapshot, "_atomic_write", fail_once)
    with pytest.raises(SnapshotRestoreError) as raised:
        execute_restore(validated, target, decisions, plan_digest=preview.plan_digest, reconcile_derived=lambda: None)
    assert raised.value.rollback_succeeded
    assert original.read_bytes() == original_bytes
    assert not (target.vault_dir / "python" / "source.md").exists()


def test_derived_failure_is_reported_after_canonical_success(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    _lesson(source.vault_dir, "python/source", "source body")
    validated = validate_snapshot(create_snapshot(source, decisions))
    preview = preview_restore(validated, target, decisions)

    def fail_derived() -> None:
        raise RuntimeError("projection unavailable")

    result = execute_restore(
        validated,
        target,
        decisions,
        plan_digest=preview.plan_digest,
        reconcile_derived=fail_derived,
    )
    assert result.canonical_restored is True
    assert result.derived_reconciled is False
    assert result.derived_error == "Derived reconciliation failed; run a maintained refresh."
    assert (target.vault_dir / "python" / "source.md").exists()


def test_restore_rolls_back_editorial_state_after_decision_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    _lesson(source.vault_dir, "python/source", "source body")
    original = _lesson(target.vault_dir, "python/current", "current body")
    JsonCandidateRepository(source.candidates_path).create(
        LessonCandidate(text="source candidate", provenance=CandidateProvenance(source_kind=SourceKind.IN_MEMORY, source_logical_name="source", source_fingerprint="source", ingested_at=datetime(2026, 8, 11, tzinfo=timezone.utc)))
    )
    target.candidates_path.parent.mkdir(parents=True)
    target.candidates_path.write_bytes(b'{"candidates":[],"schema_version":2}\n')
    candidate_before = target.candidates_path.read_bytes()
    canonical_before = original.read_bytes()
    artifact = validate_snapshot(create_snapshot(source, decisions))
    preview = preview_restore(artifact, target, decisions)
    original_replace = decisions.replace_scope
    calls = 0

    def fail_once(scope: str, entries: list[dict[str, str]]) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected editorial failure")
        original_replace(scope, entries)

    monkeypatch.setattr(decisions, "replace_scope", fail_once)
    with pytest.raises(SnapshotRestoreError) as raised:
        execute_restore(artifact, target, decisions, plan_digest=preview.plan_digest, reconcile_derived=lambda: None)
    assert raised.value.rollback_succeeded
    assert original.read_bytes() == canonical_before
    assert target.candidates_path.read_bytes() == candidate_before


def test_manifest_inventory_is_deterministic_except_creation_time(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    _lesson(source.vault_dir, "python/b", "body b")
    _lesson(source.vault_dir, "python/a", "body a")
    raw = create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        names = archive.namelist()
    assert names == sorted(names[:-1]) + ["manifest.json"]
    assert [entry["path"] for entry in manifest["files"]] == sorted(entry["path"] for entry in manifest["files"])


def test_snapshot_rejects_unsafe_source_links_and_special_entries(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (source.vault_dir / "linked.md").symlink_to(outside)
    with pytest.raises(SnapshotTargetError, match="symlinked entry"):
        create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))

    (source.vault_dir / "linked.md").unlink()
    (source.vault_dir / "linked-dir").symlink_to(tmp_path)
    with pytest.raises(SnapshotTargetError, match="symlinked entry"):
        create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))


def test_preview_is_pure_and_stale_editorial_state_is_rejected(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    _lesson(source.vault_dir, "python/source", "source body")
    current = _lesson(target.vault_dir, "python/current", "current body")
    candidate_path = target.candidates_path
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_bytes(b'{"candidates":[],"schema_version":2}\n')
    before = {path: path.read_bytes() for path in (target.vault_dir, candidate_path.parent) for path in ([path] if path.is_file() else path.rglob("*")) if path.is_file()}
    artifact = validate_snapshot(create_snapshot(source, decisions))
    preview = preview_restore(artifact, target, decisions)
    after = {path: path.read_bytes() for path in (target.vault_dir, candidate_path.parent) for path in ([path] if path.is_file() else path.rglob("*")) if path.is_file()}
    assert after == before
    assert current.exists()
    decisions.save_not_duplicates(scope=target.vault_id, left_id="a", left_fingerprint="a", right_id="b", right_fingerprint="b")
    with pytest.raises(SnapshotPlanStaleError):
        execute_restore(artifact, target, decisions, plan_digest=preview.plan_digest, reconcile_derived=lambda: None)


def test_snapshot_validation_rejects_encryption_and_case_collisions(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    _lesson(source.vault_dir, "python/source", "source body")
    raw = create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = {info.filename: archive.read(info.filename) for info in archive.infolist()}

    encrypted = bytearray(raw)
    local = encrypted.find(b"PK\x03\x04")
    central = encrypted.find(b"PK\x01\x02")
    assert local >= 0 and central >= 0
    encrypted[local + 6] |= 0x01
    encrypted[central + 8] |= 0x01
    with pytest.raises(SnapshotValidationError, match="encrypted"):
        validate_snapshot(bytes(encrypted))

    case_collision = io.BytesIO()
    with zipfile.ZipFile(case_collision, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
        archive.writestr("canonical/PYTHON/source.md", b"x")
    with pytest.raises(SnapshotValidationError, match="case-colliding"):
        validate_snapshot(case_collision.getvalue())


def test_snapshot_api_requires_preview_and_restores_explicit_registered_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    source_path = tmp_path / "source"
    target_path = tmp_path / "target"
    source_path.mkdir()
    target_path.mkdir()
    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache))
    monkeypatch.setenv("LELE_VAULT_DIR", str(source_path))
    store = VaultRegistryStore()
    source = store.bootstrap()
    target = store.register("Target", target_path)
    _lesson(source_path, "python/source", "source body")
    _lesson(target_path, "python/old", "old body")
    client = TestClient(app)

    artifact_response = client.get(f"/vaults/{source.id}/snapshot")
    assert artifact_response.status_code == 200
    artifact = artifact_response.content
    assert client.post(f"/vaults/{target.id}/restore", content=artifact).status_code == 422

    preview = client.post(f"/vaults/{target.id}/restore/preview", content=artifact)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["target_vault_id"] == target.id
    assert body["source_vault_id"] == source.id
    assert body["removals"] == ["python/old.md"]

    restored = client.post(
        f"/vaults/{target.id}/restore",
        params={"plan_digest": body["plan_digest"]},
        content=artifact,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["canonical_restored"] is True
    assert (target_path / "python" / "source.md").exists()
    assert not (target_path / "python" / "old.md").exists()
    malformed = _with_manifest(
        artifact,
        lambda manifest: manifest.__setitem__("canonical_files", [{"bad": "value"}]),
    )
    malformed_response = client.post(f"/vaults/{target.id}/restore/preview", content=malformed)
    assert malformed_response.status_code == 422
    assert malformed_response.json()["detail"]["code"] == "snapshot_invalid"


@pytest.mark.parametrize("value", [{"bad": "value"}, ["nested"], "ok", 2])
def test_manifest_canonical_paths_are_typed_before_set_or_sort(tmp_path: Path, value: object) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    _lesson(source.vault_dir, "python/source", "source body")
    raw = create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))
    if value == "ok":
        value = ["python/source.md", {"bad": "value"}]
    artifact = _with_manifest(raw, lambda manifest: manifest.__setitem__("canonical_files", [value]))
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(artifact)


@pytest.mark.parametrize("field", ["schema_version", "size"])
def test_manifest_boolean_numeric_fields_are_rejected(tmp_path: Path, field: str) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    _lesson(source.vault_dir, "python/source", "source body")
    raw = create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))

    def mutate(manifest: dict[str, object]) -> None:
        if field == "schema_version":
            manifest[field] = True
        else:
            files = manifest["files"]
            assert isinstance(files, list)
            files[0][field] = True

    with pytest.raises(SnapshotValidationError):
        validate_snapshot(_with_manifest(raw, mutate))


def test_snapshot_rejects_nonportable_source_paths_and_oversized_file_before_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    _lesson(source.vault_dir, "python/a", "lower")
    _lesson(source.vault_dir, "python/A", "upper")
    with pytest.raises(SnapshotValidationError, match="portable"):
        create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))

    (source.vault_dir / "python" / "A.md").unlink()
    huge = source.vault_dir / "huge.md"
    with huge.open("wb") as handle:
        handle.truncate(33 * 1024 * 1024)
    monkeypatch.setattr(Path, "read_bytes", lambda _: pytest.fail("unbounded read_bytes was used"))
    with pytest.raises(SnapshotTargetError, match="size limits"):
        create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))


def test_snapshot_rejects_scoped_parent_links_before_external_read_or_restore(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    _lesson(source.vault_dir, "python/source", "source")
    original = _lesson(target.vault_dir, "python/target", "target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    target.candidates_path.parent.mkdir(parents=True)
    source.candidates_path.parent.mkdir(parents=True)
    source.candidates_path.write_bytes(b'{"candidates":[],"schema_version":2}\n')
    target.candidates_path.parent.rmdir()
    target.candidates_path.parent.symlink_to(source.candidates_path.parent, target_is_directory=True)
    external_before = source.candidates_path.read_bytes()
    with pytest.raises(SnapshotTargetError, match="managed directory is unsafe"):
        preview_restore(validate_snapshot(create_snapshot(source, decisions)), target, decisions)
    assert source.candidates_path.read_bytes() == external_before
    assert original.exists()


def test_validation_detects_nonadjacent_file_descendant_collision(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    _lesson(source.vault_dir, "python/source", "source")
    raw = create_snapshot(source, DuplicateDecisionStore(tmp_path / "decisions.json"))
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source_zip, zipfile.ZipFile(output, "w") as destination:
        for info in source_zip.infolist():
            destination.writestr(info.filename, source_zip.read(info.filename))
        destination.writestr("canonical/a.md", b"x")
        destination.writestr("canonical/a.md-foo.md", b"x")
        destination.writestr("canonical/a.md/b.md", b"x")
    with pytest.raises(SnapshotValidationError, match="directory/file"):
        validate_snapshot(output.getvalue())


def test_registered_snapshot_context_does_not_bootstrap_absent_cache_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    cache = tmp_path / "missing-cache"
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    registered = VaultRegistryStore().bootstrap()
    assert not cache.exists()
    context = VaultRegistryStore().safe_context_for_registered(registered.id)
    assert context.topic_model_path == cache / "vaults" / registered.id / "topic_model.joblib"
    assert not cache.exists()


def test_restore_rejects_cache_scope_link_before_canonical_mutation(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    _lesson(source.vault_dir, "python/source", "source")
    original = _lesson(target.vault_dir, "python/target", "target")
    artifact = validate_snapshot(create_snapshot(source, decisions))
    preview = preview_restore(artifact, target, decisions)
    external = tmp_path / "external-cache"
    external.mkdir()
    target.topic_model_path.parent.parent.mkdir(parents=True)
    target.topic_model_path.parent.symlink_to(external, target_is_directory=True)
    with pytest.raises(SnapshotTargetError, match="managed directory is unsafe"):
        execute_restore(artifact, target, decisions, plan_digest=preview.plan_digest, reconcile_derived=lambda: None)
    assert original.exists()
    assert not (external / "topic_model.joblib").exists()


def test_restore_rejects_complete_context_flip_and_reconciles_with_final_context(tmp_path: Path) -> None:
    source = _context(tmp_path / "source", SOURCE_ID, "Source")
    target = _context(tmp_path / "target", TARGET_ID, "Target")
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    _lesson(source.vault_dir, "python/source", "source")
    artifact = validate_snapshot(create_snapshot(source, decisions))
    preview = preview_restore(artifact, target, decisions)
    changed = ActiveVaultContext(
        target.vault_id,
        target.display_name,
        target.vault_dir,
        target.projection_path.with_name("other.jsonl"),
        target.candidates_path,
        target.topic_model_path,
        target.duplicate_decision_scope,
    )
    calls = [target, changed]
    with pytest.raises(SnapshotPlanStaleError, match="selected Vault changed"):
        execute_restore(
            artifact,
            target,
            decisions,
            plan_digest=preview.plan_digest,
            reconcile_derived=lambda _context: None,
            resolve_current_target=lambda: calls.pop(0),
        )
