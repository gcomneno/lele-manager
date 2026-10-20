"""Synthetic cross-Vault authority regressions for issue #264."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.lesson_candidate import CandidateStorageError
from lele_manager.application.lesson_deletion import (
    LessonDeletionStorageError,
    delete_canonical_lesson_source,
)
from lele_manager.application.lesson_writing import (
    CanonicalLessonWriteStorageError,
    read_canonical_lesson_snapshot,
)
from lele_manager.application.assistant_context import resolve_assistant_context_lesson_ids
from lele_manager.composition import projection_store
from lele_manager.core.projection_store import ProjectionStoreError
from lele_manager.core.vault import (
    build_vault_tree,
    import_vault_to_jsonl,
    write_lesson_markdown,
)
from lele_manager.core.vault_filesystem import VaultFilesystemError
from lele_manager.core.vault_registry import (
    VaultConflictError,
    VaultPathError,
    VaultRegistryCorruptError,
    VaultRegistryStore,
)
from lele_manager.core.vault_snapshot import SnapshotTargetError, read_canonical_markdown_files


@pytest.fixture
def vaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("LELE_VAULT_DIR", str(a))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    store = VaultRegistryStore()
    first = store.bootstrap()
    second = store.register("B", b)
    return store, store.context_for(first), store.context_for(second)


def _lesson(root: Path, body: str = "private body") -> Path:
    return write_lesson_markdown(
        root, lesson_id="shared", body=body, topic="test", source="note",
        importance=3, tags=[], date="2026-10-20", relative_path="lesson.md",
    )


@pytest.mark.parametrize("kind", ["relative", "null_path", "alias_id", "duplicate_id", "nested", "duplicate_field"])
def test_invalid_authority_is_not_rewritten_or_bypassed(vaults, kind):
    store, a, b = vaults
    data = json.loads(store.path.read_text())
    records = {entry["id"]: entry for entry in data["vaults"]}
    if kind == "relative":
        records[a.vault_id]["path"] = "relative/vault"
    elif kind == "null_path":
        records[a.vault_id]["path"] = "/invalid\0root"
    elif kind == "alias_id":
        alias = a.vault_id.replace("-", "")
        records[b.vault_id]["id"] = alias
    elif kind == "duplicate_id":
        records[b.vault_id]["id"] = a.vault_id
    elif kind == "nested":
        records[b.vault_id]["path"] = str(a.vault_dir / "nested")
    raw = json.dumps(data)
    if kind == "duplicate_field":
        raw = raw.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
    store.path.write_text(raw)
    with pytest.raises(VaultRegistryCorruptError):
        store.context()
    assert store.path.read_text() == raw


def test_substituted_registered_root_cannot_redirect_reads_writes_or_activation(vaults):
    store, a, b = vaults
    _lesson(b.vault_dir, "B secret")
    original = a.vault_dir.with_name("a-original")
    a.vault_dir.rename(original)
    a.vault_dir.symlink_to(b.vault_dir, target_is_directory=True)
    before = store.path.read_bytes()
    for operation in (store.context, lambda: store.activate(b.vault_id), lambda: store.safe_context_for_registered(a.vault_id)):
        with pytest.raises(VaultRegistryCorruptError):
            operation()
    with pytest.raises(ValueError):
        _lesson(a.vault_dir, "overwrite")
    assert (b.vault_dir / "lesson.md").read_text().endswith("B secret\n")
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("conflict", ["nested", "parent", "name", "state"])
def test_rejected_create_does_not_make_directories(vaults, tmp_path, conflict):
    store, a, _b = vaults
    target = a.vault_dir / "new" / "nested"
    name = "new"
    if conflict == "parent":
        target = tmp_path
    elif conflict == "name":
        target = tmp_path / "unrelated" / "new"
        name = a.display_name
    elif conflict == "state":
        target = a.candidates_path.parent / "canonical"
    existed = target.exists()
    before = store.path.read_bytes()
    with pytest.raises((VaultConflictError, VaultPathError)):
        store.create(name, target)
    assert target.exists() == existed
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("link", ["file", "directory", "hardlink"])
def test_canonical_reads_import_ask_and_snapshot_refuse_foreign_links(vaults, link):
    _store, a, b = vaults
    source = _lesson(b.vault_dir, "B secret")
    before = source.read_bytes()
    if link == "file":
        (a.vault_dir / "foreign.md").symlink_to(source)
    elif link == "directory":
        (a.vault_dir / "foreign").symlink_to(b.vault_dir, target_is_directory=True)
    else:
        os.link(source, a.vault_dir / "foreign.md")
    with pytest.raises(VaultFilesystemError):
        build_vault_tree(a.vault_dir)
    with pytest.raises(VaultFilesystemError):
        import_vault_to_jsonl(a.vault_dir, a.projection_path)
    with pytest.raises(CanonicalLessonWriteStorageError):
        read_canonical_lesson_snapshot(vault_dir=a.vault_dir, lesson_id="shared")
    with pytest.raises(CanonicalLessonWriteStorageError):
        resolve_assistant_context_lesson_ids(lesson_ids=["shared"], context=a)
    with pytest.raises(LessonDeletionStorageError):
        delete_canonical_lesson_source(vault_dir=a.vault_dir, lesson_id="shared", invalidate_cache=lambda: None)
    with pytest.raises(SnapshotTargetError):
        read_canonical_markdown_files(a.vault_dir)
    assert source.read_bytes() == before
    assert not a.projection_path.exists()


@pytest.mark.parametrize("relative", ["../b/stolen.md", "/outside.md", "linked/new.md", "hard.md"])
def test_canonical_write_rejects_escape_before_mkdir(vaults, relative):
    _store, a, b = vaults
    source = _lesson(b.vault_dir)
    (a.vault_dir / "linked").symlink_to(b.vault_dir, target_is_directory=True)
    os.link(source, a.vault_dir / "hard.md")
    before = source.read_bytes()
    with pytest.raises(ValueError):
        write_lesson_markdown(a.vault_dir, lesson_id="other", body="bad", topic="test", source="note", importance=3, tags=[], date="2026-10-20", relative_path=relative)
    assert source.read_bytes() == before
    assert not (b.vault_dir / "new.md").exists()


@pytest.mark.parametrize("artifact", ["projection_path", "candidates_path", "topic_model_path", "revision_history_path"])
@pytest.mark.parametrize("link", ["file", "scope"])
def test_context_refuses_foreign_derived_or_editorial_state(vaults, artifact, link):
    store, a, b = vaults
    foreign = getattr(b, artifact)
    target = getattr(a, artifact)
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("B private state")
    target.parent.parent.mkdir(parents=True, exist_ok=True)
    if link == "scope":
        target.parent.symlink_to(foreign.parent, target_is_directory=True)
    else:
        target.parent.mkdir(exist_ok=True)
        target.symlink_to(foreign)
    with pytest.raises(VaultPathError):
        store.context()
    assert foreign.read_text() == "B private state"


def test_captured_context_and_colliding_ids_remain_scoped_after_switch(vaults, monkeypatch):
    store, a, b = vaults
    _lesson(a.vault_dir, "A private")
    _lesson(b.vault_dir, "B private")
    import_vault_to_jsonl(a.vault_dir, a.projection_path)
    import_vault_to_jsonl(b.vault_dir, b.projection_path)
    store.activate(b.vault_id)
    monkeypatch.setenv("LELE_VAULT_DIR", str(a.vault_dir))
    monkeypatch.setenv("LELE_DATA_PATH", str(a.projection_path))
    monkeypatch.setenv("LELE_MODEL_PATH", str(a.topic_model_path))
    assert store.context().vault_id == b.vault_id
    assert "A private" in resolve_assistant_context_lesson_ids(lesson_ids=["shared"], context=a).lessons[0].text
    assert "B private" in resolve_assistant_context_lesson_ids(lesson_ids=["shared"], context=store.context()).lessons[0].text
    assert projection_store(a.projection_path).snapshot().get("shared")["text"] == "A private"
    assert projection_store(b.projection_path).snapshot().get("shared")["text"] == "B private"


def test_artifact_adapters_recheck_ownership_after_context_capture(vaults):
    _store, a, b = vaults
    b.projection_path.parent.mkdir(parents=True)
    b.projection_path.write_text('{"id":"shared","text":"B secret"}\n')
    a.projection_path.parent.mkdir(parents=True)
    a.projection_path.symlink_to(b.projection_path)
    before = b.projection_path.read_bytes()
    with pytest.raises(ProjectionStoreError):
        projection_store(a.projection_path).snapshot()
    with pytest.raises(ProjectionStoreError):
        projection_store(a.projection_path).publish([])
    a.candidates_path.symlink_to(b.projection_path)
    with pytest.raises(CandidateStorageError):
        JsonCandidateRepository(a.candidates_path).list()
    assert b.projection_path.read_bytes() == before


def test_cli_approval_captures_one_context(vaults, monkeypatch):
    from lele_manager.cli import tritalele

    _store, a, b = vaults
    calls = []

    def resolve():
        calls.append(True)
        return a if len(calls) == 1 else b

    seen = []
    monkeypatch.setattr(tritalele, "active_vault_context", resolve)
    monkeypatch.setattr(tritalele, "JsonCandidateRepository", lambda path: seen.append(path))
    tritalele._approval_service()
    assert calls == [True]
    assert seen == [a.candidates_path]


def test_activation_refuses_linked_canonical_input_without_switch_or_projection(vaults):
    from fastapi import HTTPException
    from lele_manager.api import server

    store, a, b = vaults
    source = _lesson(a.vault_dir, "A secret")
    (b.vault_dir / "foreign.md").symlink_to(source)
    before = source.read_bytes()
    with pytest.raises(HTTPException) as rejected:
        server.activate_vault(b.vault_id)
    assert rejected.value.status_code == 503
    assert store.active().id == a.vault_id
    assert not b.projection_path.exists()
    assert source.read_bytes() == before


def test_ask_and_snapshot_fail_closed_before_exposing_linked_content(vaults, monkeypatch):
    from fastapi import HTTPException
    from lele_manager.api import server

    _store, a, b = vaults
    source = _lesson(b.vault_dir, "B secret")
    (a.vault_dir / "foreign.md").symlink_to(source)
    calls = []
    monkeypatch.setattr(server, "_ask_vault_service", lambda: calls.append(True))
    with pytest.raises(HTTPException) as rejected:
        server.ask_vault(server.AskVaultRequest(question="secret?", lesson_ids=["shared"]))
    assert rejected.value.status_code == 503
    assert "B secret" not in str(rejected.value.detail)
    assert calls == []
    with pytest.raises(HTTPException) as rejected:
        server.download_vault_snapshot(a.vault_id)
    assert rejected.value.status_code == 409
    assert "B secret" not in str(rejected.value.detail)


def test_model_access_refuses_redirected_model_before_deserialization(vaults, monkeypatch):
    from lele_manager.ml import topic_model

    _store, a, b = vaults
    b.topic_model_path.parent.mkdir(parents=True)
    b.topic_model_path.write_bytes(b"foreign model")
    a.topic_model_path.parent.mkdir(parents=True)
    a.topic_model_path.symlink_to(b.topic_model_path)
    calls = []
    monkeypatch.setattr(topic_model.joblib, "load", lambda path: calls.append(path))
    monkeypatch.setattr(topic_model.joblib, "dump", lambda *args: calls.append(args))
    with pytest.raises(VaultFilesystemError):
        topic_model.load_topic_model(a.topic_model_path)
    with pytest.raises(VaultFilesystemError):
        topic_model.save_topic_model(object(), a.topic_model_path)
    assert calls == []
    assert b.topic_model_path.read_bytes() == b"foreign model"


def test_restore_into_inactive_vault_keeps_other_scopes_and_reports_refresh_failure(vaults, tmp_path):
    from lele_manager.core.duplicate_decisions import DuplicateDecisionStore
    from lele_manager.core.vault_snapshot import create_snapshot, validate_snapshot, preview_restore, execute_restore

    store, a, b = vaults
    _lesson(a.vault_dir, "A backup")
    _lesson(b.vault_dir, "B original")
    third = store.create("C", tmp_path / "c")
    c = store.context_for(third)
    c_lesson = _lesson(c.vault_dir, "C private")
    c.projection_path.parent.mkdir(parents=True)
    c.projection_path.write_text("C projection")
    c_before = c_lesson.read_bytes(), c.projection_path.read_bytes()
    a_before = (a.vault_dir / "lesson.md").read_bytes()
    decisions = DuplicateDecisionStore(tmp_path / "decisions.json")
    artifact = validate_snapshot(create_snapshot(a, decisions))
    preview = preview_restore(artifact, b, decisions)

    def failed_refresh(context):
        assert context == b
        raise RuntimeError("synthetic refresh failure")

    result = execute_restore(
        artifact, b, decisions, plan_digest=preview.plan_digest,
        reconcile_derived=failed_refresh,
        resolve_current_target=lambda: store.safe_context_for_registered(b.vault_id),
        mutation_boundary=store.mutation_boundary,
    )
    assert result.canonical_restored is True
    assert result.derived_reconciled is False
    assert (b.vault_dir / "lesson.md").read_bytes() == a_before
    assert (a.vault_dir / "lesson.md").read_bytes() == a_before
    assert (c_lesson.read_bytes(), c.projection_path.read_bytes()) == c_before
    assert store.active().id == a.vault_id


def test_existing_uuid_spelling_is_preserved_without_identity_migration(vaults):
    store, a, _b = vaults
    data = json.loads(store.path.read_text())
    alias = a.vault_id.replace("-", "")
    for entry in data["vaults"]:
        if entry["id"] == a.vault_id:
            entry["id"] = alias
    data["active_vault_id"] = alias
    data["legacy_migration"]["vault_id"] = alias
    store.path.write_text(json.dumps(data))
    before = store.path.read_bytes()
    assert store.context().vault_id == alias
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("operation", ["publish", "verify"])
def test_approval_adapter_rejects_linked_destination_without_foreign_mutation(vaults, operation):
    from lele_manager.adapters.canonical_markdown_vault import FilesystemCanonicalMarkdownVault
    from lele_manager.application.candidate_approval import CanonicalLessonSpec, CanonicalVaultStorageError

    _store, a, b = vaults
    source = _lesson(b.vault_dir, "B secret")
    a.vault_dir.rename(a.vault_dir.with_name("a-original"))
    a.vault_dir.symlink_to(b.vault_dir, target_is_directory=True)
    before = source.read_bytes()
    lesson = CanonicalLessonSpec(
        lesson_id="new", relative_path="new.md", body="new body", topic="test",
        source="note", importance=3, tags=(), date="2026-10-20", title="New", provenance={},
    )
    with pytest.raises(CanonicalVaultStorageError):
        getattr(FilesystemCanonicalMarkdownVault(a.vault_dir), operation)(lesson)
    assert source.read_bytes() == before
    assert not (b.vault_dir / "new.md").exists()
