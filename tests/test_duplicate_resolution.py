from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.application.lesson_deletion import LessonDeletionStorageError
from lele_manager.application.lesson_writing import CanonicalLessonWriteStorageError
from lele_manager.core.duplicate_decisions import (
    DuplicateDecisionStore,
    material_fingerprint,
)
from lele_manager.core.vault import find_markdown_by_id, import_vault_to_jsonl, write_lesson_markdown
from lele_manager.core.vault_registry import active_vault_context


@pytest.fixture
def duplicate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setattr(server, "DATA_PATH", None)
    monkeypatch.setattr(server, "MODEL_PATH", None)
    monkeypatch.setattr(server, "DUPLICATE_DECISIONS_PATH", tmp_path / "app" / "duplicate-decisions.json")
    for lesson_id, title, body in (
        ("alpha/a", "Nearly same A", "The exact reviewed knowledge."),
        ("alpha/b", "Nearly same B", "The exact reviewed knowledge."),
    ):
        write_lesson_markdown(
            vault, lesson_id=lesson_id, body=body, topic="alpha", source="note",
            importance=3, tags=["one", "two"], date="2026-08-10", title=title,
        )
    context = active_vault_context()
    import_vault_to_jsonl(vault, context.projection_path)
    return vault, context.projection_path


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
    context = active_vault_context()
    assert not store.is_suppressed(
        scope="different-registered-vault-id", left_id="alpha/a",
        left_fingerprint=pair["left_fingerprint"], right_id="alpha/b",
        right_fingerprint=pair["right_fingerprint"],
    )
    saved = json.loads(server.get_duplicate_decisions_path().read_text(encoding="utf-8"))
    assert saved["schema_version"] == 2
    assert context.vault_id in saved["scopes"]


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
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setattr(server, "DUPLICATE_DECISIONS_PATH", tmp_path / "decisions.json")
    monkeypatch.setattr(server, "DATA_PATH", None)
    monkeypatch.setattr(server, "MODEL_PATH", None)
    frame = pd.DataFrame([
        {"id": "a", "text": "top", "topic": "x"},
        {"id": "b", "text": "top", "topic": "x"},
        {"id": "c", "text": "lower", "topic": "x"},
        {"id": "d", "text": "lower", "topic": "x"},
    ])
    monkeypatch.setattr(server, "load_lessons_df", lambda *_args: frame)
    top_left, top_right = frame.iloc[0].to_dict(), frame.iloc[1].to_dict()
    DuplicateDecisionStore(server.get_duplicate_decisions_path()).save_not_duplicates(
        scope=active_vault_context().vault_id, left_id="a", left_fingerprint=material_fingerprint(top_left),
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


def test_materially_changed_lesson_reappears_after_a_suppressed_decision(
    duplicate_env: tuple[Path, Path],
) -> None:
    vault, data = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    marked = client.post("/duplicates/not-duplicates", json=pair)
    assert marked.status_code == 200, marked.text
    assert _report(client)["total_pairs"] == 0

    # Keep the exact body but change canonical title: fingerprints, not the
    # detector, decide whether the old suppression is still valid.
    write_lesson_markdown(
        vault, lesson_id="alpha/a", body="The exact reviewed knowledge.", topic="alpha", source="note",
        importance=3, tags=["one", "two"], date="2026-08-10", title="Materially changed A",
    )
    import_vault_to_jsonl(vault, data)
    reappeared = _report(client)
    assert reappeared["total_pairs"] == 1
    assert reappeared["suppressed_pairs"] == 0


def test_malformed_decision_store_keeps_review_read_only_and_refuses_writes(
    duplicate_env: tuple[Path, Path],
) -> None:
    _, _ = duplicate_env
    path = server.get_duplicate_decisions_path()
    path.parent.mkdir(parents=True)
    corrupt = b"{not-json"
    path.write_bytes(corrupt)
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    response = client.post("/duplicates/not-duplicates", json=pair)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "duplicate_decision_store_failed"
    assert path.read_bytes() == corrupt


def test_merge_writes_selected_survivor_then_deletes_other_once(
    duplicate_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault, data = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    calls = 0
    original_refresh = server._sync_vault_import

    def refresh_once(context: object = None) -> object:
        nonlocal calls
        calls += 1
        return original_refresh(context)

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


@pytest.mark.parametrize(
    ("survivor_id", "superseded_id", "survivor_fingerprint_key", "superseded_fingerprint_key"),
    [
        ("alpha/a", "alpha/b", "left_fingerprint", "right_fingerprint"),
        ("alpha/b", "alpha/a", "right_fingerprint", "left_fingerprint"),
    ],
)
def test_merge_preserves_the_explicit_survivor_path(
    duplicate_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
    survivor_id: str, superseded_id: str, survivor_fingerprint_key: str, superseded_fingerprint_key: str,
) -> None:
    vault, _ = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    refreshes = 0
    original_refresh = server._sync_vault_import

    def refresh_once(context: object = None) -> object:
        nonlocal refreshes
        refreshes += 1
        return original_refresh(context)

    monkeypatch.setattr(server, "_sync_vault_import", refresh_once)
    response = client.post("/duplicates/merge", json={
        "survivor_id": survivor_id, "superseded_id": superseded_id,
        "expected_survivor_fingerprint": pair[survivor_fingerprint_key],
        "expected_superseded_fingerprint": pair[superseded_fingerprint_key],
        "result": {"text": f"Reviewed {survivor_id}", "title": "Reviewed", "topic": "alpha", "source": "note", "importance": 3, "tags": ["one"], "date": "2026-08-10"},
    })
    assert response.status_code == 200, response.text
    assert find_markdown_by_id(vault, survivor_id) is not None
    assert find_markdown_by_id(vault, superseded_id) is None
    assert refreshes == 1


def test_merge_write_failure_does_not_delete_or_refresh(
    duplicate_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault, _ = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    before = find_markdown_by_id(vault, "alpha/a").read_bytes()
    deletes = 0
    refreshes = 0

    def fail_write(**_: object) -> Path:
        raise CanonicalLessonWriteStorageError("write failed")

    def counted_delete(**_: object) -> object:
        nonlocal deletes
        deletes += 1
        raise AssertionError("delete must not follow a failed write")

    def counted_refresh() -> None:
        nonlocal refreshes
        refreshes += 1

    monkeypatch.setattr(server, "write_canonical_lesson_source", fail_write)
    monkeypatch.setattr(server, "delete_canonical_lesson_source", counted_delete)
    monkeypatch.setattr(server, "_sync_vault_import", counted_refresh)
    response = client.post("/duplicates/merge", json={
        "survivor_id": "alpha/a", "superseded_id": "alpha/b",
        "expected_survivor_fingerprint": pair["left_fingerprint"], "expected_superseded_fingerprint": pair["right_fingerprint"],
        "result": {"text": "new", "topic": "alpha", "source": "note", "importance": 3, "tags": [], "date": "2026-08-10"},
    })
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "duplicate_merge_write_failed"
    assert find_markdown_by_id(vault, "alpha/a").read_bytes() == before
    assert find_markdown_by_id(vault, "alpha/b") is not None
    assert deletes == 0 and refreshes == 0


@pytest.mark.parametrize("refresh_fails", [False, True])
def test_merge_delete_failure_keeps_written_survivor_and_reports_truth(
    duplicate_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, refresh_fails: bool,
) -> None:
    vault, _ = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    refreshes = 0

    def fail_delete(**_: object) -> object:
        raise LessonDeletionStorageError("delete failed")

    def refresh(_context: object = None) -> None:
        nonlocal refreshes
        refreshes += 1
        if refresh_fails:
            raise RuntimeError("refresh failed")

    monkeypatch.setattr(server, "delete_canonical_lesson_source", fail_delete)
    monkeypatch.setattr(server, "_sync_vault_import", refresh)
    response = client.post("/duplicates/merge", json={
        "survivor_id": "alpha/a", "superseded_id": "alpha/b",
        "expected_survivor_fingerprint": pair["left_fingerprint"], "expected_superseded_fingerprint": pair["right_fingerprint"],
        "result": {"text": "Reviewed survivor", "topic": "alpha", "source": "note", "importance": 3, "tags": [], "date": "2026-08-10"},
    })
    assert response.status_code == (503 if refresh_fails else 200)
    payload = response.json()["detail"]["recovery"] if refresh_fails else response.json()
    assert payload["completed"] is False
    assert payload["survivor_written"] is True
    assert payload["superseded_deleted"] is False
    assert payload["failure"]["code"] == "duplicate_merge_superseded_delete_failed"
    assert payload["refresh_outcome"] == {"attempted": True, "refreshed": not refresh_fails}
    assert "Reviewed survivor" in find_markdown_by_id(vault, "alpha/a").read_text(encoding="utf-8")
    assert find_markdown_by_id(vault, "alpha/b") is not None
    assert refreshes == 1


def test_merge_refresh_failure_after_full_canonical_success(
    duplicate_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault, _ = duplicate_env
    client = TestClient(server.app)
    pair = _report(client)["pairs"][0]
    monkeypatch.setattr(server, "_sync_vault_import", lambda: (_ for _ in ()).throw(RuntimeError("refresh failed")))
    response = client.post("/duplicates/merge", json={
        "survivor_id": "alpha/b", "superseded_id": "alpha/a",
        "expected_survivor_fingerprint": pair["right_fingerprint"], "expected_superseded_fingerprint": pair["left_fingerprint"],
        "result": {"text": "Reviewed right", "topic": "alpha", "source": "note", "importance": 3, "tags": [], "date": "2026-08-10"},
    })
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "duplicate_merge_refresh_failed"
    assert detail["recovery"]["survivor_written"] is True
    assert detail["recovery"]["superseded_deleted"] is True
    assert detail["recovery"]["refresh_outcome"] == {"attempted": True, "refreshed": False}
    assert "Reviewed right" in find_markdown_by_id(vault, "alpha/b").read_text(encoding="utf-8")
    assert find_markdown_by_id(vault, "alpha/a") is None


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
