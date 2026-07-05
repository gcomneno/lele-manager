from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server as server_mod
from lele_manager.api.server import app
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
