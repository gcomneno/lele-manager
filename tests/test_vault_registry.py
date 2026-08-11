from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.api.server import app
from lele_manager.core.vault_registry import (
    VaultConflictError,
    VaultRegistryCorruptError,
    VaultRegistryStore,
)
from lele_manager.core.duplicate_decisions import DuplicateDecisionStore


def test_bootstrap_uses_legacy_vault_once(monkeypatch: pytest.MonkeyPatch, tmp_path):
    vault_a = tmp_path / "a"
    vault_a.mkdir()
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault_a))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data-root"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache-root"))
    store = VaultRegistryStore(tmp_path / "data" / "vault-registry.json")
    initial = store.bootstrap()
    vault_b = tmp_path / "b"
    vault_b.mkdir()
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault_b))
    assert store.context().vault_id == initial.id
    assert store.context().vault_dir == vault_a.resolve()


def test_registry_rejects_duplicate_and_overlapping_paths(tmp_path):
    root = tmp_path / "knowledge"
    nested = root / "work"
    root.mkdir()
    nested.mkdir()
    store = VaultRegistryStore(tmp_path / "data" / "vault-registry.json")
    store.bootstrap = lambda: None  # type: ignore[method-assign]
    # Establish a valid registry without relying on process environment.
    first = {"schema_version": 1, "active_vault_id": "00000000-0000-4000-8000-000000000001", "vaults": [{"id": "00000000-0000-4000-8000-000000000001", "name": "Main", "path": str(root.resolve()), "registered_at": "2026-01-01T00:00:00+00:00"}]}
    store.path.parent.mkdir(parents=True)
    store.path.write_text(json.dumps(first), encoding="utf-8")
    with pytest.raises(VaultConflictError):
        store.register("Nested", nested)
    with pytest.raises(VaultConflictError):
        store.register("Again", root)


def test_registry_lifecycle_keeps_runtime_artifacts_and_candidates_isolated(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    vault_a, vault_b = tmp_path / "a", tmp_path / "b"
    vault_a.mkdir()
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault_a))
    store = VaultRegistryStore()
    a = store.bootstrap()
    b = store.create("Second", vault_b)
    renamed = store.rename(b.id, "Renamed")
    assert renamed.name == "Renamed"
    context_a, context_b = store.context_for(a), store.context_for(renamed)
    assert context_a.candidates_path != context_b.candidates_path
    assert context_a.projection_path != context_b.projection_path
    assert context_a.topic_model_path != context_b.topic_model_path
    with pytest.raises(VaultConflictError):
        store.remove(a.id)
    store.remove(renamed.id)
    assert [item.id for item in store.list()] == [a.id]


def test_bootstrap_migrates_path_scoped_duplicate_decisions_to_stable_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    vault = tmp_path / "vault"
    vault.mkdir()
    data = tmp_path / "data"
    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    decisions = data / "duplicate-decisions.json"
    decisions.parent.mkdir()
    decisions.write_text(json.dumps({
        "schema_version": 1,
        "scopes": {str(vault.resolve()): [{
            "left_id": "a", "right_id": "b", "left_fingerprint": "left",
            "right_fingerprint": "right", "decided_at": "2026-08-11T00:00:00+00:00",
        }]},
    }), encoding="utf-8")
    active = VaultRegistryStore().bootstrap()
    assert DuplicateDecisionStore(decisions).is_suppressed(
        scope=active.id, left_id="a", left_fingerprint="left",
        right_id="b", right_fingerprint="right",
    )


def test_corrupt_registry_is_not_replaced(tmp_path):
    path = tmp_path / "data" / "vault-registry.json"
    path.parent.mkdir(parents=True)
    raw = b"not json"
    path.write_bytes(raw)
    with pytest.raises(VaultRegistryCorruptError):
        VaultRegistryStore(path).context()
    assert path.read_bytes() == raw


def test_api_activation_scopes_projection_and_preserves_markdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    vault_a, vault_b = tmp_path / "a", tmp_path / "b"
    vault_a.mkdir()
    vault_b.mkdir()
    markdown_a = vault_a / "shared.md"
    markdown_b = vault_b / "shared.md"
    markdown_a.write_text("---\nid: shared/id\ntopic: a\n---\nA body\n", encoding="utf-8")
    markdown_b.write_text("---\nid: shared/id\ntopic: b\n---\nB body\n", encoding="utf-8")
    before = markdown_b.read_bytes()
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "app-cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault_a))
    monkeypatch.setattr(server, "DATA_PATH", None)
    monkeypatch.setattr(server, "MODEL_PATH", None)
    client = TestClient(app)
    active_a = client.get("/vault/status").json()
    registered = client.post("/vaults/register", json={"name": "B", "path": str(vault_b)})
    assert registered.status_code == 201
    activated = client.post(f"/vaults/{registered.json()['id']}/activate")
    assert activated.status_code == 200
    assert activated.json()["vault_id"] != active_a["vault_id"]
    assert markdown_b.read_bytes() == before
    assert "B body" in client.get("/lessons/shared/id").json()["text"]
    assert "A body" not in client.get("/lessons/shared/id").json()["text"]
