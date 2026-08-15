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
