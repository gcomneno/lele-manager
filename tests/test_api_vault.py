from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server as server_mod
from lele_manager.api.server import app
from lele_manager.core.doctor import DoctorOperationalError
from lele_manager.composition import projection_store
from lele_manager.core.vault import (
    build_vault_tree,
    find_markdown_by_id,
    import_vault_to_jsonl,
    write_lesson_markdown,
)
from lele_manager.core.vault_registry import VaultRegistryStore


@pytest.fixture
def vault_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    vault.mkdir()
    data = tmp_path / "lessons.jsonl"
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setattr(server_mod, "DATA_PATH", data)
    return vault, data


def test_write_and_find_markdown(vault_env: tuple[Path, Path]) -> None:
    vault, _ = vault_env
    write_lesson_markdown(
        vault,
        lesson_id="python/2026-07-05.pytest",
        body="Body test",
        topic="python",
        source="note",
        importance=4,
        tags=["python", "pytest"],
        date="2026-07-05",
        title="Pytest tip",
    )
    found = find_markdown_by_id(vault, "python/2026-07-05.pytest")
    assert found is not None
    text = found.read_text(encoding="utf-8")
    assert "id: python/2026-07-05.pytest" in text
    assert "Body test" in text


def test_build_vault_tree(vault_env: tuple[Path, Path]) -> None:
    vault, _ = vault_env
    (vault / "python").mkdir()
    (vault / "python" / "2026-07-05.a.md").write_text("---\nid: x\n---\n", encoding="utf-8")
    tree = build_vault_tree(vault)
    assert tree.type == "dir"
    assert tree.children
    assert any(c.name == "python" for c in tree.children)


def test_import_vault_to_jsonl(vault_env: tuple[Path, Path]) -> None:
    vault, data = vault_env
    write_lesson_markdown(
        vault,
        lesson_id="git/2026-07-05.branch",
        body="Branch flow",
        topic="git",
        source="note",
        importance=3,
        tags=["git"],
        date="2026-07-05",
    )
    result = import_vault_to_jsonl(vault, data)
    assert result["n_lessons"] == 1
    assert data.is_file()


def test_api_vault_tree_and_save(vault_env: tuple[Path, Path]) -> None:
    vault, data = vault_env
    client = TestClient(app)

    status = client.get("/vault/status")
    assert status.status_code == 200
    assert status.json()["exists"] is True

    create = client.post(
        "/vault/lessons",
        json={
            "text": "Nuova lesson da GUI",
            "topic": "python",
            "source": "note",
            "importance": 4,
            "tags": ["python"],
            "date": "2026-07-05",
            "title": "GUI save",
        },
    )
    assert create.status_code == 201, create.text
    lesson_id = create.json()["id"]
    assert lesson_id

    tree = client.get("/vault/tree")
    assert tree.status_code == 200
    assert "python" in str(tree.json())

    detail = client.get(f"/lessons/{lesson_id}")
    assert detail.status_code == 200
    canonical_revision = detail.json()["canonical_revision"]

    update = client.put(
        f"/lessons/{lesson_id}",
        json={
            "text": "Lesson aggiornata",
            "topic": "python",
            "source": "note",
            "importance": 5,
            "tags": ["python"],
            "date": "2026-07-05",
            "expected_revision": canonical_revision,
        },
    )
    assert update.status_code == 200
    assert "aggiornata" in update.json()["text"]

    md = find_markdown_by_id(vault, lesson_id)
    assert md is not None
    assert "aggiornata" in md.read_text(encoding="utf-8")


def test_api_ops_refresh(vault_env: tuple[Path, Path]) -> None:
    vault, data = vault_env
    write_lesson_markdown(
        vault,
        lesson_id="linux/2026-07-05.rsync",
        body="rsync -a",
        topic="linux",
        source="note",
        importance=3,
        tags=["linux"],
        date="2026-07-05",
    )
    client = TestClient(app)
    resp = client.post("/ops/refresh?train=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["import_result"]["n_lessons"] >= 1
    assert data.is_file()


def test_api_vault_doctor_returns_read_only_report(
    vault_env: tuple[Path, Path],
) -> None:
    vault, _ = vault_env
    valid = write_lesson_markdown(
        vault,
        lesson_id="python/2026-07-05.valid",
        body="Valid lesson",
        topic="python",
        source="note",
        importance=3,
        tags=["python"],
        date="2026-07-05",
        title="Valid",
    )
    broken = vault / "python" / "broken.md"
    broken.write_text("No frontmatter\n", encoding="utf-8")
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in (valid, broken)
    }

    response = TestClient(app).get("/vault/doctor")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "valid": False,
        "files_checked": 2,
        "checked_files": ["python/2026-07-05.valid.md", "python/broken.md"],
        "unique_ids": 1,
        "error_count": 1,
        "problems": [
            {
                "code": "missing_frontmatter",
                "message": "frontmatter YAML assente",
                "path": "python/broken.md",
                "field": None,
                "severity": "error",
            }
        ],
    }
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in before
    } == before


def test_api_vault_doctor_returns_not_found_for_missing_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    existing = tmp_path / "registered-vault"
    existing.mkdir()
    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(existing))
    store = VaultRegistryStore()
    active = store.bootstrap()
    missing = tmp_path / "missing-vault"
    store.path.write_text(
        '{"schema_version": 1, "active_vault_id": "' + active.id
        + '", "vaults": [{"id": "' + active.id + '", "name": "Missing", "path": "'
        + str(missing) + '", "registered_at": "' + active.registered_at + '"}]}',
        encoding="utf-8",
    )

    response = TestClient(app).get("/vault/doctor")

    assert response.status_code == 404
    assert "Vault directory not found" in response.json()["detail"]


def test_api_vault_doctor_returns_server_error_for_operational_failure(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_doctor(*_args: object, **_kwargs: object) -> None:
        raise DoctorOperationalError("vault inspection failed")

    monkeypatch.setattr(server_mod, "check_markdown_files", fail_doctor)

    response = TestClient(app).get("/vault/doctor")

    assert response.status_code == 500
    assert response.json()["detail"] == "vault inspection failed"


def _write_delete_fixture(vault: Path) -> tuple[Path, Path]:
    target = write_lesson_markdown(
        vault,
        lesson_id="distributed-systems/2026-08-10.retry-semantics",
        body="Retry only when the canonical operation did not happen.",
        topic="distributed-systems",
        source="note",
        importance=4,
        tags=["retry"],
        date="2026-08-10",
        title="Retry semantics",
        relative_path="archive/source-of-truth.md",
    )
    other = write_lesson_markdown(
        vault,
        lesson_id="distributed-systems/2026-08-10.other",
        body="The other lesson remains.",
        topic="distributed-systems",
        source="note",
        importance=3,
        tags=["other"],
        date="2026-08-10",
        title="Other lesson",
    )
    return target, other


def test_delete_lesson_removes_exact_canonical_file_then_refreshes_projection(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    target, other = _write_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)
    refresh_called = False
    original_refresh = server_mod._sync_vault_import

    def checked_refresh(context: object = None) -> object:
        nonlocal refresh_called
        refresh_called = True
        assert not target.exists()
        return original_refresh(context)

    monkeypatch.setattr(server_mod, "_sync_vault_import", checked_refresh)
    response = TestClient(app).delete(
        "/lessons/distributed-systems%2F2026-08-10.retry-semantics"
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "lesson_id": "distributed-systems/2026-08-10.retry-semantics",
        "relative_vault_path": "archive/source-of-truth.md",
        "canonical_deleted": True,
        "refresh_outcome": {"refreshed": True},
    }
    assert refresh_called
    assert not target.exists()
    assert other.exists()
    assert [row["id"] for row in projection_store(data).snapshot().list()] == [
        "distributed-systems/2026-08-10.other"
    ]
    assert TestClient(app).get(
        "/lessons/distributed-systems%2F2026-08-10.retry-semantics/similar"
    ).status_code == 404


def test_delete_lesson_wrong_id_does_not_mutate_or_refresh(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    target, other = _write_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)
    before = data.read_bytes()

    def forbidden_refresh() -> None:
        raise AssertionError("refresh must not run for a wrong ID")

    monkeypatch.setattr(server_mod, "_sync_vault_import", forbidden_refresh)
    response = TestClient(app).delete("/lessons/distributed-systems%2Fmissing")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "lesson_not_found"
    assert target.exists()
    assert other.exists()
    assert data.read_bytes() == before


def test_delete_lesson_reports_partial_refresh_after_canonical_delete(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    target, other = _write_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)

    def failed_refresh(_context: object = None) -> None:
        assert not target.exists()
        raise OSError("projection unavailable")

    monkeypatch.setattr(server_mod, "_sync_vault_import", failed_refresh)
    response = TestClient(app).delete(
        "/lessons/distributed-systems%2F2026-08-10.retry-semantics"
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "lesson_deleted_refresh_failed"
    assert detail["recovery"] == {
        "canonical_deleted": True,
        "lesson_id": "distributed-systems/2026-08-10.retry-semantics",
        "relative_vault_path": "archive/source-of-truth.md",
    }
    assert not target.exists()
    assert other.exists()
    # No rollback/recreation and no projection-only repair happened.
    assert "retry-semantics" in data.read_text(encoding="utf-8")


def test_delete_lesson_storage_failure_does_not_refresh_or_claim_success(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    target, _ = _write_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)

    def fail_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == target.resolve():
            raise OSError("read-only storage")
        return original_unlink(self, *args, **kwargs)

    def forbidden_refresh() -> None:
        raise AssertionError("refresh must not run after canonical delete failure")

    original_unlink = Path.unlink
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    monkeypatch.setattr(server_mod, "_sync_vault_import", forbidden_refresh)
    response = TestClient(app).delete(
        "/lessons/distributed-systems%2F2026-08-10.retry-semantics"
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "lesson_delete_storage_failed"
    assert "recovery" not in response.json()["detail"]
    assert target.exists()


def test_delete_last_lesson_publishes_an_empty_projection(
    vault_env: tuple[Path, Path],
) -> None:
    vault, data = vault_env
    target = write_lesson_markdown(
        vault,
        lesson_id="only/lesson",
        body="Only lesson.",
        topic="only",
        source="note",
        importance=3,
        tags=[],
        date="2026-08-10",
    )
    import_vault_to_jsonl(vault, data)

    response = TestClient(app).delete("/lessons/only%2Flesson")

    assert response.status_code == 200, response.text
    assert not target.exists()
    assert list(vault.rglob("*.md")) == []
    assert data.is_file()
    assert data.read_text(encoding="utf-8") == ""
    assert projection_store(data).snapshot().list() == ()
    assert TestClient(app).get("/lessons/only%2Flesson").status_code == 404


def _write_bulk_delete_fixture(vault: Path) -> dict[str, Path]:
    return {
        lesson_id: write_lesson_markdown(
            vault,
            lesson_id=lesson_id,
            body=f"Body for {lesson_id}.",
            topic="bulk",
            source="note",
            importance=3,
            tags=[],
            date="2026-08-10",
            title=lesson_id.rsplit("/", 1)[-1],
        )
        for lesson_id in ("bulk/a", "bulk/b", "bulk/c")
    }


def test_bulk_delete_removes_only_requested_sources_and_refreshes_once(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    paths = _write_bulk_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)
    original_refresh = server_mod._sync_vault_import
    refresh_count = 0

    def checked_refresh(context: object = None) -> object:
        nonlocal refresh_count
        refresh_count += 1
        assert not paths["bulk/a"].exists()
        assert not paths["bulk/b"].exists()
        assert paths["bulk/c"].exists()
        return original_refresh(context)

    monkeypatch.setattr(server_mod, "_sync_vault_import", checked_refresh)
    response = TestClient(app).post(
        "/lessons/bulk-delete", json={"lesson_ids": ["bulk/a", "bulk/b"]}
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "requested_count": 2,
        "deleted": [
            {"lesson_id": "bulk/a", "relative_vault_path": "bulk/a.md"},
            {"lesson_id": "bulk/b", "relative_vault_path": "bulk/b.md"},
        ],
        "failed": [],
        "refresh_outcome": {"attempted": True, "refreshed": True},
    }
    assert refresh_count == 1
    assert not paths["bulk/a"].exists()
    assert not paths["bulk/b"].exists()
    assert paths["bulk/c"].exists()
    assert [row["id"] for row in projection_store(data).snapshot().list()] == ["bulk/c"]


def test_bulk_delete_continues_after_not_found_and_storage_failure(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    paths = _write_bulk_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)
    original_unlink = Path.unlink
    original_refresh = server_mod._sync_vault_import
    refresh_count = 0

    def fail_b_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == paths["bulk/b"].resolve():
            raise OSError("read-only storage")
        return original_unlink(self, *args, **kwargs)

    def checked_refresh(context: object = None) -> object:
        nonlocal refresh_count
        refresh_count += 1
        assert not paths["bulk/a"].exists()
        assert not paths["bulk/c"].exists()
        assert paths["bulk/b"].exists()
        return original_refresh(context)

    monkeypatch.setattr(Path, "unlink", fail_b_unlink)
    monkeypatch.setattr(server_mod, "_sync_vault_import", checked_refresh)
    response = TestClient(app).post(
        "/lessons/bulk-delete",
        json={"lesson_ids": ["bulk/a", "bulk/missing", "bulk/b", "bulk/c"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["deleted"] == [
        {"lesson_id": "bulk/a", "relative_vault_path": "bulk/a.md"},
        {"lesson_id": "bulk/c", "relative_vault_path": "bulk/c.md"},
    ]
    assert response.json()["failed"] == [
        {"lesson_id": "bulk/missing", "code": "not_found"},
        {"lesson_id": "bulk/b", "code": "storage_error"},
    ]
    assert response.json()["refresh_outcome"] == {"attempted": True, "refreshed": True}
    assert refresh_count == 1
    assert paths["bulk/b"].exists()
    assert [row["id"] for row in projection_store(data).snapshot().list()] == ["bulk/b"]


def test_bulk_delete_all_canonical_failures_do_not_refresh(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    paths = _write_bulk_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)

    def forbidden_refresh() -> None:
        raise AssertionError("refresh must not run without canonical success")

    monkeypatch.setattr(server_mod, "_sync_vault_import", forbidden_refresh)
    response = TestClient(app).post(
        "/lessons/bulk-delete", json={"lesson_ids": ["bulk/missing"]}
    )
    assert response.status_code == 200
    assert response.json() == {
        "requested_count": 1,
        "deleted": [],
        "failed": [{"lesson_id": "bulk/missing", "code": "not_found"}],
        "refresh_outcome": {"attempted": False, "refreshed": False},
    }
    assert all(path.exists() for path in paths.values())


def test_bulk_delete_refresh_failure_returns_exact_canonical_recovery(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    paths = _write_bulk_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)

    def failed_refresh(_context: object = None) -> None:
        assert not paths["bulk/a"].exists()
        assert not paths["bulk/b"].exists()
        raise OSError("projection unavailable")

    monkeypatch.setattr(server_mod, "_sync_vault_import", failed_refresh)
    response = TestClient(app).post(
        "/lessons/bulk-delete",
        json={"lesson_ids": ["bulk/a", "bulk/missing", "bulk/b"]},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "bulk_lessons_deleted_refresh_failed"
    assert detail["recovery"] == {
        "requested_count": 3,
        "deleted": [
            {"lesson_id": "bulk/a", "relative_vault_path": "bulk/a.md"},
            {"lesson_id": "bulk/b", "relative_vault_path": "bulk/b.md"},
        ],
        "failed": [{"lesson_id": "bulk/missing", "code": "not_found"}],
        "refresh_outcome": {"attempted": True, "refreshed": False},
    }
    assert not paths["bulk/a"].exists()
    assert not paths["bulk/b"].exists()
    assert paths["bulk/c"].exists()


def test_bulk_delete_invalidates_similarity_cache_before_one_refresh(
    vault_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, data = vault_env
    paths = _write_bulk_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)
    events: list[str] = []
    original_invalidate = server_mod.invalidate_similarity_cache
    original_refresh = server_mod._sync_vault_import

    def record_invalidation() -> None:
        events.append("invalidate")
        original_invalidate()

    def checked_refresh(context: object = None) -> object:
        events.append("refresh")
        assert events.count("invalidate") == 2
        assert not paths["bulk/a"].exists()
        assert not paths["bulk/b"].exists()
        return original_refresh(context)

    monkeypatch.setattr(server_mod, "invalidate_similarity_cache", record_invalidation)
    monkeypatch.setattr(server_mod, "_sync_vault_import", checked_refresh)
    response = TestClient(app).post(
        "/lessons/bulk-delete", json={"lesson_ids": ["bulk/a", "bulk/b"]}
    )
    assert response.status_code == 200
    assert events[:3] == ["invalidate", "invalidate", "refresh"]


@pytest.mark.parametrize(
    "lesson_ids",
    [[], ["bulk/a", "bulk/a"], [" "], ["bulk/a"] * 501],
)
def test_bulk_delete_rejects_invalid_id_batches(
    vault_env: tuple[Path, Path], lesson_ids: list[str]
) -> None:
    vault, _ = vault_env
    paths = _write_bulk_delete_fixture(vault)
    response = TestClient(app).post(
        "/lessons/bulk-delete", json={"lesson_ids": lesson_ids}
    )
    assert response.status_code == 422
    assert all(path.exists() for path in paths.values())


def test_bulk_delete_can_publish_empty_projection(
    vault_env: tuple[Path, Path],
) -> None:
    vault, data = vault_env
    paths = _write_bulk_delete_fixture(vault)
    import_vault_to_jsonl(vault, data)
    response = TestClient(app).post(
        "/lessons/bulk-delete", json={"lesson_ids": ["bulk/a", "bulk/b", "bulk/c"]}
    )
    assert response.status_code == 200
    assert all(not path.exists() for path in paths.values())
    assert projection_store(data).snapshot().list() == ()


def test_revision_history_diff_and_rollback_api(
    vault_env: tuple[Path, Path],
) -> None:
    vault, _ = vault_env
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/history-api",
            "text": "Before",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["python"],
            "date": "2026-08-15",
            "title": "History API",
        },
    )
    assert created.status_code == 201, created.text

    detail = client.get("/lessons/python%2Fhistory-api")
    assert detail.status_code == 200, detail.text
    initial = detail.json()["canonical_revision"]

    edited = client.put(
        "/lessons/python%2Fhistory-api",
        json={
            "text": "After",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["python"],
            "date": "2026-08-15",
            "title": "History API",
            "expected_revision": initial,
        },
    )
    assert edited.status_code == 200, edited.text

    current = client.get("/lessons/python%2Fhistory-api").json()[
        "canonical_revision"
    ]

    history = client.get(
        "/lesson-history",
        params={"lesson_id": "python/history-api"},
    )
    assert history.status_code == 200, history.text
    assert [item["revision"] for item in history.json()["revisions"]] == [0, 1]
    assert [item["action"] for item in history.json()["revisions"]] == [
        "baseline",
        "edit",
    ]

    diff = client.get(
        "/lesson-history/diff",
        params={
            "lesson_id": "python/history-api",
            "from_revision": 0,
            "to_revision": 1,
        },
    )
    assert diff.status_code == 200, diff.text
    assert "-Before" in diff.json()["unified_diff"]
    assert "+After" in diff.json()["unified_diff"]

    rollback = client.post(
        "/lesson-history/rollback",
        json={
            "lesson_id": "python/history-api",
            "target_revision": 0,
            "expected_revision": current,
            "reason": "API rollback test",
        },
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["revision"] == 2

    after = client.get("/lessons/python%2Fhistory-api")
    assert after.status_code == 200
    assert after.json()["text"] == "Before"
    assert (
        after.json()["canonical_revision"]
        == rollback.json()["canonical_revision"]
    )

    history = client.get(
        "/lesson-history",
        params={"lesson_id": "python/history-api"},
    ).json()
    assert [item["action"] for item in history["revisions"]] == [
        "baseline",
        "edit",
        "rollback",
    ]
    assert history["revisions"][2]["rollback_from_revision"] == 0


def test_revision_aware_update_rejects_stale_external_edit(
    vault_env: tuple[Path, Path],
) -> None:
    vault, _ = vault_env
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/stale-api",
            "text": "Before",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": [],
            "date": "2026-08-15",
        },
    )
    assert created.status_code == 201

    detail = client.get("/lessons/python%2Fstale-api").json()
    stale = detail["canonical_revision"]

    target = find_markdown_by_id(vault, "python/stale-api")
    assert target is not None
    target.write_text(
        target.read_text(encoding="utf-8").replace("Before", "External"),
        encoding="utf-8",
    )

    response = client.put(
        "/lessons/python%2Fstale-api",
        json={
            "text": "Managed",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": [],
            "date": "2026-08-15",
            "expected_revision": stale,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "lesson_revision_stale"
    assert "External" in target.read_text(encoding="utf-8")


def test_revision_update_reports_canonical_success_when_refresh_fails(
    vault_env: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/partial-api",
            "text": "Before",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": [],
            "date": "2026-08-15",
        },
    )
    assert created.status_code == 201

    current = client.get("/lessons/python%2Fpartial-api").json()[
        "canonical_revision"
    ]

    def fail_refresh(_context: object = None) -> None:
        raise OSError("projection unavailable")

    monkeypatch.setattr(server_mod, "_sync_vault_import", fail_refresh)

    response = client.put(
        "/lessons/python%2Fpartial-api",
        json={
            "text": "After",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": [],
            "date": "2026-08-15",
            "expected_revision": current,
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "lesson_update_refresh_failed"
    assert detail["recovery"]["canonical_saved"] is True
    assert detail["recovery"]["revision"] == 1
    assert detail["recovery"]["refresh_outcome"]["refreshed"] is False

def test_api_relationship_detail_exposes_outgoing_incoming_and_supersedes(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    target = client.post(
        "/vault/lessons",
        json={
            "id": "python/relationship-target",
            "text": "Target.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
            "title": "Target",
        },
    )
    assert target.status_code == 201, target.text

    source = client.post(
        "/vault/lessons",
        json={
            "id": "python/relationship-source",
            "text": "Source.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
            "title": "Source",
            "lifecycle": "deprecated",
            "superseded_by": "python/relationship-target",
            "relationships": {
                "extends": ["python/relationship-target"],
                "see-also": ["python/relationship-target"],
            },
        },
    )
    assert source.status_code == 201, source.text

    source_detail = client.get(
        "/lessons/python%2Frelationship-source"
    )
    assert source_detail.status_code == 200, source_detail.text
    assert source_detail.json()["relationships"] == {
        "extends": ["python/relationship-target"],
        "see-also": ["python/relationship-target"],
    }
    assert source_detail.json()["incoming_relationships"] == {}
    assert (
        source_detail.json()["superseded_by"]
        == "python/relationship-target"
    )

    target_detail = client.get(
        "/lessons/python%2Frelationship-target"
    )
    assert target_detail.status_code == 200, target_detail.text
    assert target_detail.json()["relationships"] == {}
    assert target_detail.json()["incoming_relationships"] == {
        "extends": ["python/relationship-source"],
        "see-also": ["python/relationship-source"],
    }
    assert target_detail.json()["supersedes"] == [
        "python/relationship-source"
    ]


def test_api_relationship_update_omission_preserves_and_empty_mapping_clears(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    assert client.post(
        "/vault/lessons",
        json={
            "id": "python/relationship-target",
            "text": "Target.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
        },
    ).status_code == 201

    assert client.post(
        "/vault/lessons",
        json={
            "id": "python/relationship-source",
            "text": "Before.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
            "relationships": {
                "corrects": ["python/relationship-target"],
            },
        },
    ).status_code == 201

    before = client.get(
        "/lessons/python%2Frelationship-source"
    ).json()

    preserved = client.put(
        "/lessons/python%2Frelationship-source",
        json={
            "text": "After preserve.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
            "expected_revision": before["canonical_revision"],
        },
    )
    assert preserved.status_code == 200, preserved.text

    after_preserve = client.get(
        "/lessons/python%2Frelationship-source"
    ).json()
    assert after_preserve["relationships"] == {
        "corrects": ["python/relationship-target"],
    }

    cleared = client.put(
        "/lessons/python%2Frelationship-source",
        json={
            "text": "After preserve.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
            "relationships": {},
            "expected_revision": after_preserve["canonical_revision"],
        },
    )
    assert cleared.status_code == 200, cleared.text

    after_clear = client.get(
        "/lessons/python%2Frelationship-source"
    ).json()
    assert after_clear["relationships"] == {}

    target_detail = client.get(
        "/lessons/python%2Frelationship-target"
    ).json()
    assert target_detail["incoming_relationships"] == {}


def test_api_rejects_missing_relationship_target_before_canonical_update(
    vault_env: tuple[Path, Path],
) -> None:
    vault, _ = vault_env
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/relationship-source",
            "text": "Original.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
        },
    )
    assert created.status_code == 201, created.text

    detail = client.get(
        "/lessons/python%2Frelationship-source"
    ).json()
    canonical = find_markdown_by_id(
        vault,
        "python/relationship-source",
    )
    assert canonical is not None
    before = canonical.read_bytes()

    response = client.put(
        "/lessons/python%2Frelationship-source",
        json={
            "text": "Must not be saved.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["relationships"],
            "date": "2026-08-17",
            "relationships": {
                "see-also": ["python/missing"],
            },
            "expected_revision": detail["canonical_revision"],
        },
    )

    assert response.status_code == 400, response.text
    assert "does not exist" in response.text
    assert canonical.read_bytes() == before



def test_api_detail_exposes_review_metadata_and_explainable_age_signal(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/freshness-age",
            "text": "Knowledge worth revisiting.",
            "topic": "python",
            "source": "note",
            "importance": 5,
            "tags": ["freshness"],
            "date": "2020-01-01",
            "reviewed_at": "2020-01-01",
            "review_interval_days": 30,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["reviewed_at"] == "2020-01-01"
    assert created.json()["review_interval_days"] == 30

    detail = client.get("/lessons/python%2Ffreshness-age")
    assert detail.status_code == 200, detail.text

    payload = detail.json()
    assert payload["reviewed_at"] == "2020-01-01"
    assert payload["review_interval_days"] == 30
    assert payload["freshness"]["review_needed"] is True
    assert payload["freshness"]["review_interval_days"] == 30
    assert payload["freshness"]["age_days"] >= 30
    assert "review-overdue" in {
        reason["code"] for reason in payload["freshness"]["reasons"]
    }


def test_api_detail_exposes_relation_based_freshness_signal(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    target = client.post(
        "/vault/lessons",
        json={
            "id": "python/freshness-target",
            "text": "Earlier knowledge.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-19",
        },
    )
    assert target.status_code == 201, target.text

    correction = client.post(
        "/vault/lessons",
        json={
            "id": "python/freshness-correction",
            "text": "Newer correction.",
            "topic": "python",
            "source": "note",
            "importance": 4,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "relationships": {
                "corrects": ["python/freshness-target"],
            },
        },
    )
    assert correction.status_code == 201, correction.text

    detail = client.get("/lessons/python%2Ffreshness-target")
    assert detail.status_code == 200, detail.text

    reasons = detail.json()["freshness"]["reasons"]
    correction_reason = next(
        reason
        for reason in reasons
        if reason["code"] == "corrected-by-related-knowledge"
    )
    assert correction_reason["related_lesson_ids"] == [
        "python/freshness-correction"
    ]


def test_api_update_preserves_and_explicitly_clears_review_metadata(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/freshness-authoring",
            "text": "Before.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "reviewed_at": "2026-08-01",
            "review_interval_days": 180,
        },
    )
    assert created.status_code == 201, created.text

    before = client.get("/lessons/python%2Ffreshness-authoring").json()

    preserved = client.put(
        "/lessons/python%2Ffreshness-authoring",
        json={
            "text": "After preserve.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "expected_revision": before["canonical_revision"],
        },
    )
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["reviewed_at"] == "2026-08-01"
    assert preserved.json()["review_interval_days"] == 180

    after_preserve = client.get(
        "/lessons/python%2Ffreshness-authoring"
    ).json()

    cleared = client.put(
        "/lessons/python%2Ffreshness-authoring",
        json={
            "text": "After preserve.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "reviewed_at": None,
            "review_interval_days": None,
            "expected_revision": after_preserve["canonical_revision"],
        },
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["reviewed_at"] is None
    assert cleared.json()["review_interval_days"] is None



def test_mark_reviewed_records_explicit_review_and_activates_review_needed(
    vault_env: tuple[Path, Path],
) -> None:
    from datetime import datetime, timezone

    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/review-action",
            "text": "Needs an explicit human review.",
            "topic": "python",
            "source": "note",
            "importance": 5,
            "tags": ["freshness"],
            "date": "2025-01-01",
            "lifecycle": "review-needed",
            "review_interval_days": 180,
        },
    )
    assert created.status_code == 201, created.text

    before = client.get("/lessons/python%2Freview-action")
    assert before.status_code == 200, before.text
    before_payload = before.json()
    assert before_payload["lifecycle"] == "review-needed"
    assert before_payload["reviewed_at"] is None

    expected_reviewed_at = datetime.now(timezone.utc).date().isoformat()

    reviewed = client.post(
        "/lessons/python%2Freview-action/review",
        json={
            "expected_revision": before_payload["canonical_revision"],
        },
    )
    assert reviewed.status_code == 200, reviewed.text

    payload = reviewed.json()
    assert payload["lesson_id"] == "python/review-action"
    assert payload["reviewed_at"] == expected_reviewed_at
    assert payload["lifecycle"] == "active"
    assert payload["canonical_changed"] is True
    assert payload["revision"] == 1
    assert payload["refresh_outcome"]["refreshed"] is True

    after = client.get("/lessons/python%2Freview-action")
    assert after.status_code == 200, after.text
    after_payload = after.json()

    assert after_payload["reviewed_at"] == expected_reviewed_at
    assert after_payload["review_interval_days"] == 180
    assert after_payload["lifecycle"] == "active"
    assert (
        after_payload["canonical_revision"]
        == payload["canonical_revision"]
    )


def test_mark_reviewed_preserves_canonical_provenance(
    vault_env: tuple[Path, Path],
) -> None:
    from datetime import datetime, timezone

    from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
    from lele_manager.core.vault import import_vault_to_jsonl, write_lesson_markdown

    vault, projection = vault_env
    provenance = {
        "source_kind": "markdown",
        "source_logical_name": "source.md",
        "source_fingerprint": "sha256:source",
        "run_metadata": {"batch": 7},
        "transformations": [{"kind": "extract"}],
    }

    canonical = write_lesson_markdown(
        vault,
        lesson_id="python/review-provenance",
        body="Canonical knowledge with maintained provenance.",
        topic="python",
        source="note",
        importance=4,
        tags=["freshness"],
        date="2026-08-20",
        title="Review provenance",
        provenance=provenance,
        lifecycle="review-needed",
        review_interval_days=180,
    )
    import_vault_to_jsonl(vault, projection)

    client = TestClient(app)
    before = client.get("/lessons/python%2Freview-provenance")
    assert before.status_code == 200, before.text

    reviewed = client.post(
        "/lessons/python%2Freview-provenance/review",
        json={
            "expected_revision": before.json()["canonical_revision"],
        },
    )
    assert reviewed.status_code == 200, reviewed.text

    frontmatter, _ = parse_markdown_with_frontmatter(
        canonical.read_text(encoding="utf-8")
    )

    assert frontmatter["provenance"] == provenance
    assert str(frontmatter["reviewed_at"]) == datetime.now(
        timezone.utc
    ).date().isoformat()
    assert "lifecycle" not in frontmatter
    assert frontmatter["review_interval_days"] == 180


def test_mark_reviewed_rejects_malformed_canonical_provenance_without_mutation(
    vault_env: tuple[Path, Path],
) -> None:
    from lele_manager.core.vault import import_vault_to_jsonl, write_lesson_markdown

    vault, projection = vault_env
    canonical = write_lesson_markdown(
        vault,
        lesson_id="python/review-invalid-provenance",
        body="Canonical knowledge.",
        topic="python",
        source="note",
        importance=3,
        tags=["freshness"],
        date="2026-08-20",
        title="Invalid provenance",
        provenance={1: "invalid"},  # type: ignore[dict-item]
        lifecycle="review-needed",
    )
    import_vault_to_jsonl(vault, projection)

    client = TestClient(app)
    before = client.get("/lessons/python%2Freview-invalid-provenance")
    assert before.status_code == 200, before.text

    canonical_before = canonical.read_bytes()

    reviewed = client.post(
        "/lessons/python%2Freview-invalid-provenance/review",
        json={
            "expected_revision": before.json()["canonical_revision"],
        },
    )

    assert reviewed.status_code == 503, reviewed.text
    assert reviewed.json()["detail"]["code"] == "lesson_review_write_failed"
    assert canonical.read_bytes() == canonical_before


def test_mark_reviewed_same_day_is_revision_aware_noop(
    vault_env: tuple[Path, Path],
) -> None:
    from datetime import datetime, timezone

    client = TestClient(app)
    today = datetime.now(timezone.utc).date().isoformat()

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/review-noop",
            "text": "Already reviewed today.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "reviewed_at": today,
        },
    )
    assert created.status_code == 201, created.text

    canonical = find_markdown_by_id(vault_env[0], "python/review-noop")
    assert canonical is not None
    canonical_text = canonical.read_text(encoding="utf-8")
    marker = "\n\nAlready reviewed today.\n"
    assert canonical_text.count(marker) == 1
    canonical.write_text(
        canonical_text.replace(
            marker,
            "\n\n  Already reviewed today.  \n\n\n",
            1,
        ),
        encoding="utf-8",
    )
    import_vault_to_jsonl(vault_env[0], vault_env[1])
    canonical_before = canonical.read_bytes()

    before = client.get("/lessons/python%2Freview-noop").json()

    reviewed = client.post(
        "/lessons/python%2Freview-noop/review",
        json={
            "expected_revision": before["canonical_revision"],
        },
    )
    assert reviewed.status_code == 200, reviewed.text

    payload = reviewed.json()
    assert payload["reviewed_at"] == today
    assert payload["lifecycle"] == "active"
    assert payload["canonical_changed"] is False
    assert payload["revision"] is None
    assert payload["refresh_outcome"]["refreshed"] is False
    assert canonical.read_bytes() == canonical_before

    history = client.get(
        "/lesson-history",
        params={"lesson_id": "python/review-noop"},
    )
    assert history.status_code == 200, history.text
    assert history.json()["revisions"] == []


def test_mark_reviewed_rejects_stale_revision_without_mutating_review_metadata(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/review-stale",
            "text": "Original.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "lifecycle": "review-needed",
        },
    )
    assert created.status_code == 201, created.text

    before = client.get("/lessons/python%2Freview-stale").json()
    stale_revision = before["canonical_revision"]

    edited = client.put(
        "/lessons/python%2Freview-stale",
        json={
            "text": "Changed before review.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "expected_revision": stale_revision,
        },
    )
    assert edited.status_code == 200, edited.text

    rejected = client.post(
        "/lessons/python%2Freview-stale/review",
        json={"expected_revision": stale_revision},
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "lesson_revision_stale"

    after = client.get("/lessons/python%2Freview-stale")
    assert after.status_code == 200, after.text
    assert after.json()["reviewed_at"] is None
    assert after.json()["lifecycle"] == "review-needed"


def test_mark_reviewed_surfaces_partial_success_when_refresh_fails(
    vault_env: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    created = client.post(
        "/vault/lessons",
        json={
            "id": "python/review-partial",
            "text": "Review me.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "lifecycle": "review-needed",
        },
    )
    assert created.status_code == 201, created.text

    before = client.get("/lessons/python%2Freview-partial").json()

    def fail_refresh(_context: object = None) -> None:
        raise OSError("projection unavailable")

    monkeypatch.setattr(server_mod, "_sync_vault_import", fail_refresh)

    response = client.post(
        "/lessons/python%2Freview-partial/review",
        json={
            "expected_revision": before["canonical_revision"],
        },
    )

    assert response.status_code == 503, response.text
    detail = response.json()["detail"]

    assert detail["code"] == "lesson_review_refresh_failed"
    assert detail["recovery"]["canonical_saved"] is True
    assert detail["recovery"]["lifecycle"] == "active"
    assert detail["recovery"]["reviewed_at"]
    assert detail["recovery"]["refresh_outcome"] == {
        "attempted": True,
        "refreshed": False,
    }



def test_search_can_filter_derived_freshness_without_changing_lifecycle(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    old = client.post(
        "/vault/lessons",
        json={
            "id": "python/search-review-needed",
            "text": "Old active knowledge.",
            "topic": "python",
            "source": "note",
            "importance": 4,
            "tags": ["freshness"],
            "date": "2020-01-01",
            "review_interval_days": 30,
        },
    )
    assert old.status_code == 201, old.text

    recent = client.post(
        "/vault/lessons",
        json={
            "id": "python/search-fresh",
            "text": "Recent active knowledge.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
        },
    )
    assert recent.status_code == 201, recent.text

    needs_review = client.post(
        "/lessons/search",
        json={
            "topic_in": ["python"],
            "lifecycle_in": ["active"],
            "freshness_review_needed": True,
            "limit": 50,
        },
    )
    assert needs_review.status_code == 200, needs_review.text
    assert {
        item["id"] for item in needs_review.json()
    } == {"python/search-review-needed"}

    fresh = client.post(
        "/lessons/search",
        json={
            "topic_in": ["python"],
            "lifecycle_in": ["active"],
            "freshness_review_needed": False,
            "limit": 50,
        },
    )
    assert fresh.status_code == 200, fresh.text
    assert {
        item["id"] for item in fresh.json()
    } == {"python/search-fresh"}

    detail = client.get(
        "/lessons/python%2Fsearch-review-needed"
    ).json()
    assert detail["lifecycle"] == "active"
    assert detail["freshness"]["review_needed"] is True


def test_search_freshness_filter_keeps_incoming_relation_evidence(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    target = client.post(
        "/vault/lessons",
        json={
            "id": "python/search-relation-target",
            "text": "Target knowledge.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-19",
        },
    )
    assert target.status_code == 201, target.text

    correction = client.post(
        "/vault/lessons",
        json={
            "id": "python/search-relation-correction",
            "text": "Correcting knowledge.",
            "topic": "other",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
            "relationships": {
                "corrects": ["python/search-relation-target"],
            },
        },
    )
    assert correction.status_code == 201, correction.text

    response = client.post(
        "/lessons/search",
        json={
            "topic_in": ["python"],
            "lifecycle_in": ["active"],
            "freshness_review_needed": True,
            "limit": 50,
        },
    )
    assert response.status_code == 200, response.text
    assert {
        item["id"] for item in response.json()
    } == {"python/search-relation-target"}


def test_dashboard_reports_bounded_derived_review_count(
    vault_env: tuple[Path, Path],
) -> None:
    client = TestClient(app)

    old = client.post(
        "/vault/lessons",
        json={
            "id": "python/dashboard-review",
            "text": "Needs review.",
            "topic": "python",
            "source": "note",
            "importance": 5,
            "tags": ["freshness"],
            "date": "2020-01-01",
            "review_interval_days": 30,
        },
    )
    assert old.status_code == 201, old.text

    recent = client.post(
        "/vault/lessons",
        json={
            "id": "python/dashboard-fresh",
            "text": "Fresh.",
            "topic": "python",
            "source": "note",
            "importance": 3,
            "tags": ["freshness"],
            "date": "2026-08-20",
        },
    )
    assert recent.status_code == 201, recent.text

    response = client.get("/dashboard/summary")
    assert response.status_code == 200, response.text

    freshness = response.json()["freshness"]
    assert freshness["review_needed"] == 1
    assert freshness["default_review_interval_days"] == 365
    assert freshness["as_of"]
