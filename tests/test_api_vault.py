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

    update = client.put(
        f"/lessons/{lesson_id}",
        json={
            "text": "Lesson aggiornata",
            "topic": "python",
            "source": "note",
            "importance": 5,
            "tags": ["python"],
            "date": "2026-07-05",
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
    monkeypatch.setenv("LELE_VAULT_DIR", str(tmp_path / "missing-vault"))

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

    def checked_refresh() -> object:
        nonlocal refresh_called
        refresh_called = True
        assert not target.exists()
        return original_refresh()

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

    def failed_refresh() -> None:
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
