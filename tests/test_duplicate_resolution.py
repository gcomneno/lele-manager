from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.core.duplicate_decisions import (
    DuplicateDecisionStore,
    current_vault_scope,
    material_fingerprint,
)
from lele_manager.core.vault import find_markdown_by_id, import_vault_to_jsonl, write_lesson_markdown


@pytest.fixture
def duplicate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    vault.mkdir()
    data = tmp_path / "lessons.jsonl"
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setattr(server, "DATA_PATH", data)
    monkeypatch.setattr(server, "DUPLICATE_DECISIONS_PATH", tmp_path / "app" / "duplicate-decisions.json")
    for lesson_id, title, body in (
        ("alpha/a", "Nearly same A", "The exact reviewed knowledge."),
        ("alpha/b", "Nearly same B", "The exact reviewed knowledge."),
    ):
        write_lesson_markdown(
            vault, lesson_id=lesson_id, body=body, topic="alpha", source="note",
            importance=3, tags=["one", "two"], date="2026-08-10", title=title,
        )
    import_vault_to_jsonl(vault, data)
    return vault, data


def _report(client: TestClient) -> dict:
    response = client.get("/duplicates", params={"exact_only": "true", "limit": 100})
    assert response.status_code == 200, response.text
    return response.json()


def test_not_duplicates_persists_orientation_independently_and_is_scoped(
    duplicate_env: tuple[Path, Path], tmp_path: Path,
) -> None:
    vault, _ = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    response = client.post("/duplicates/not-duplicates", json={
        "left_id": pair["right_id"], "right_id": pair["left_id"],
        "left_fingerprint": pair["right_fingerprint"], "right_fingerprint": pair["left_fingerprint"],
    })
    assert response.status_code == 200, response.text
    assert _report(client)["total_pairs"] == 0

    store = DuplicateDecisionStore(server.get_duplicate_decisions_path())
    assert not store.is_suppressed(
        scope=current_vault_scope(tmp_path / "other-vault"), left_id="alpha/a",
        left_fingerprint=pair["left_fingerprint"], right_id="alpha/b",
        right_fingerprint=pair["right_fingerprint"],
    )
    saved = json.loads(server.get_duplicate_decisions_path().read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert current_vault_scope(vault) in saved["scopes"]


def test_material_fingerprint_ignores_tag_order_but_not_material_changes() -> None:
    base = {
        "text": "Text\r\n", "title": " Title ", "topic": "Alpha", "source": "Note",
        "importance": 3, "tags": ["Two", "one"], "date": "2026-08-10",
    }
    assert material_fingerprint(base) == material_fingerprint({**base, "tags": ["ONE", "two"]})
    assert material_fingerprint(base) != material_fingerprint({**base, "text": "Changed text"})
    assert material_fingerprint(base) != material_fingerprint({**base, "tags": ["two", "three"]})


def test_suppression_precedes_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setattr(server, "DUPLICATE_DECISIONS_PATH", tmp_path / "decisions.json")
    frame = pd.DataFrame([
        {"id": "a", "text": "top", "topic": "x"},
        {"id": "b", "text": "top", "topic": "x"},
        {"id": "c", "text": "lower", "topic": "x"},
        {"id": "d", "text": "lower", "topic": "x"},
    ])
    monkeypatch.setattr(server, "load_lessons_df", lambda: frame)
    top_left, top_right = frame.iloc[0].to_dict(), frame.iloc[1].to_dict()
    DuplicateDecisionStore(server.get_duplicate_decisions_path()).save_not_duplicates(
        scope=current_vault_scope(vault), left_id="a", left_fingerprint=material_fingerprint(top_left),
        right_id="b", right_fingerprint=material_fingerprint(top_right),
    )
    report = server.duplicates(min_score=0.85, exact_only=True, limit=1)
    assert report.suppressed_pairs == 1
    assert [(pair.left_id, pair.right_id) for pair in report.pairs] == [("c", "d")]


def test_not_duplicates_rejects_stale_canonical_fingerprint(
    duplicate_env: tuple[Path, Path],
) -> None:
    vault, data = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    write_lesson_markdown(
        vault, lesson_id="alpha/a", body="Changed canonical knowledge.", topic="alpha", source="note",
        importance=3, tags=["one", "two"], date="2026-08-10", title="Nearly same A",
    )
    response = client.post("/duplicates/not-duplicates", json=pair)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_pair_stale"
    assert not server.get_duplicate_decisions_path().exists()
    assert data.exists()


def test_merge_writes_selected_survivor_then_deletes_other_once(
    duplicate_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault, data = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    calls = 0
    original_refresh = server._sync_vault_import

    def refresh_once() -> object:
        nonlocal calls
        calls += 1
        return original_refresh()

    monkeypatch.setattr(server, "_sync_vault_import", refresh_once)
    response = client.post("/duplicates/merge", json={
        "survivor_id": "alpha/b", "superseded_id": "alpha/a",
        "expected_survivor_fingerprint": pair["right_fingerprint"],
        "expected_superseded_fingerprint": pair["left_fingerprint"],
        "result": {"text": "Human reviewed merged result.", "title": "Merged", "topic": "alpha", "source": "manual", "importance": 5, "tags": ["merged"], "date": "2026-08-11"},
    })
    assert response.status_code == 200, response.text
    assert response.json()["completed"] is True
    assert calls == 1
    assert find_markdown_by_id(vault, "alpha/a") is None
    survivor = find_markdown_by_id(vault, "alpha/b")
    assert survivor is not None and "Human reviewed merged result." in survivor.read_text(encoding="utf-8")
    assert "alpha/b" in data.read_text(encoding="utf-8")


def test_merge_stale_request_does_not_write_or_delete(duplicate_env: tuple[Path, Path]) -> None:
    vault, _ = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    before = {path: path.read_bytes() for path in vault.rglob("*.md")}
    write_lesson_markdown(vault, lesson_id="alpha/a", body="Changed.", topic="alpha", source="note", importance=3, tags=[], date="2026-08-10", title="A")
    response = client.post("/duplicates/merge", json={
        "survivor_id": "alpha/a", "superseded_id": "alpha/b",
        "expected_survivor_fingerprint": pair["left_fingerprint"],
        "expected_superseded_fingerprint": pair["right_fingerprint"],
        "result": {"text": "should not write", "topic": "alpha", "source": "note", "importance": 3, "tags": [], "date": "2026-08-10"},
    })
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_pair_stale"
    assert find_markdown_by_id(vault, "alpha/b") is not None
    assert find_markdown_by_id(vault, "alpha/a").read_bytes() != before[find_markdown_by_id(vault, "alpha/a")]


def test_ambiguous_canonical_id_is_never_deleted(duplicate_env: tuple[Path, Path]) -> None:
    vault, _ = duplicate_env
    first = vault / "duplicate-one.md"
    second = vault / "duplicate-two.md"
    first.write_text("---\nid: ambiguous\n---\nfirst", encoding="utf-8")
    second.write_text("---\nid: ambiguous\n---\nsecond", encoding="utf-8")
    response = TestClient(server.app).delete("/lessons/ambiguous")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "lesson_delete_storage_failed"
    assert first.exists() and second.exists()
