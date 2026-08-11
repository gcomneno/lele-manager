from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import numpy as np

from lele_manager.api import server
from lele_manager.composition import projection_store
from lele_manager.core.vault import write_lesson_markdown
from lele_manager.core.vault_registry import ActiveVaultContext


def _context(root: Path, label: str) -> ActiveVaultContext:
    vault = root / label
    vault.mkdir(parents=True)
    return ActiveVaultContext(
        vault_id=label,
        display_name=label,
        vault_dir=vault,
        projection_path=root / "data" / label / "lessons.jsonl",
        candidates_path=root / "data" / label / "candidates.json",
        topic_model_path=root / "cache" / label / "topic_model.joblib",
        duplicate_decision_scope=label,
    )


def _flipping_resolver(
    monkeypatch: pytest.MonkeyPatch,
    first: ActiveVaultContext,
    second: ActiveVaultContext,
) -> list[ActiveVaultContext]:
    calls: list[ActiveVaultContext] = []

    def resolve() -> ActiveVaultContext:
        context = first if not calls else second
        calls.append(context)
        return context

    monkeypatch.setattr(server, "get_active_vault_context", resolve)
    return calls


def _lesson_payload(text: str) -> dict[str, object]:
    return {
        "text": text,
        "topic": "topic",
        "source": "note",
        "importance": 3,
        "tags": [],
        "date": "2026-08-11",
    }


def _write_canonical(vault: Path, lesson_id: str, text: str) -> None:
    payload = _lesson_payload(text)
    write_lesson_markdown(
        vault,
        lesson_id=lesson_id,
        body=str(payload.pop("text")),
        **payload,
    )


def test_duplicates_uses_one_context_for_projection_model_and_decision_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _context(tmp_path, "A"), _context(tmp_path, "B")
    for lesson_id in ("topic/a", "topic/b"):
        _write_canonical(first.vault_dir, lesson_id, "same")
    calls = _flipping_resolver(monkeypatch, first, second)
    seen: dict[str, object] = {}
    frame = pd.DataFrame([{"id": "topic/a", "text": "same"}, {"id": "topic/b", "text": "same"}])

    monkeypatch.setattr(server, "load_lessons_df", lambda context: seen.setdefault("projection", context) and frame)
    monkeypatch.setattr(
        server,
        "build_similarity_index",
        lambda _df, context: seen.setdefault("model", context)
        and SimpleNamespace(transformer=object(), feature_matrix=np.eye(2)),
    )

    class Decisions:
        def is_suppressed(self, **kwargs: object) -> bool:
            seen["scope"] = kwargs["scope"]
            return False

    monkeypatch.setattr(server, "DuplicateDecisionStore", lambda _path: Decisions())
    report = server.duplicates(min_score=0.8, limit=None, exact_only=False)

    assert report.total_pairs == 1
    assert seen == {"projection": first, "model": first, "scope": "A"}
    assert calls == [first]


def test_merge_refresh_stays_with_mutated_vault_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _context(tmp_path, "A"), _context(tmp_path, "B")
    for lesson_id in ("topic/a", "topic/b"):
        _write_canonical(first.vault_dir, lesson_id, "same")
    calls = _flipping_resolver(monkeypatch, first, second)
    survivor = server._canonical_duplicate_lesson(first.vault_dir, "topic/a")
    superseded = server._canonical_duplicate_lesson(first.vault_dir, "topic/b")
    refreshed: list[ActiveVaultContext] = []
    monkeypatch.setattr(server, "_sync_vault_import", lambda context: refreshed.append(context))

    response = server.merge_duplicates(
        server.DuplicateMergeRequest(
            survivor_id="topic/a",
            superseded_id="topic/b",
            expected_survivor_fingerprint=server.material_fingerprint(survivor),
            expected_superseded_fingerprint=server.material_fingerprint(superseded),
            result=server.LessonVaultWrite(**_lesson_payload("merged")),
        )
    )

    assert response.completed is True
    assert refreshed == [first]
    assert calls == [first]


def test_single_and_bulk_delete_bind_refresh_to_first_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _context(tmp_path, "A"), _context(tmp_path, "B")
    for lesson_id in ("topic/a", "topic/b", "topic/c"):
        _write_canonical(first.vault_dir, lesson_id, lesson_id)
    refreshed: list[ActiveVaultContext] = []
    monkeypatch.setattr(server, "_sync_vault_import", lambda context: refreshed.append(context))

    single_calls = _flipping_resolver(monkeypatch, first, second)
    assert server.delete_lesson("topic/a").canonical_deleted is True
    assert refreshed == [first]
    assert single_calls == [first]

    bulk_calls = _flipping_resolver(monkeypatch, first, second)
    result = server.bulk_delete_lessons(server.BulkLessonDeleteRequest(lesson_ids=["topic/b", "topic/c"]))
    assert result.refresh_outcome.refreshed is True
    assert refreshed == [first, first]
    assert bulk_calls == [first]


def test_vault_write_readback_uses_the_write_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _context(tmp_path, "A"), _context(tmp_path, "B")
    projection_store(second.projection_path).publish([
        {"id": "topic/new", **_lesson_payload("from B")},
    ])

    create_calls = _flipping_resolver(monkeypatch, first, second)
    created = server.create_vault_lesson(
        server.LessonVaultCreate(id="topic/new", **_lesson_payload("from A"))
    )
    assert created.text == "from A"
    assert create_calls == [first]

    projection_store(second.projection_path).publish([
        {"id": "topic/new", **_lesson_payload("still from B")},
    ])
    update_calls = _flipping_resolver(monkeypatch, first, second)
    updated = server.update_lesson("topic/new", server.LessonVaultWrite(**_lesson_payload("updated A")))
    assert updated.text == "updated A"
    assert update_calls == [first]


def test_dashboard_summary_uses_one_context_for_every_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _context(tmp_path, "A"), _context(tmp_path, "B")
    _write_canonical(first.vault_dir, "topic/a", "from A")
    projection_store(first.projection_path).publish([
        {"id": "topic/a", **_lesson_payload("from A")},
    ])
    second.topic_model_path.parent.mkdir(parents=True)
    second.topic_model_path.write_bytes(b"model B")
    calls = _flipping_resolver(monkeypatch, first, second)

    summary = server.dashboard_summary()

    assert summary.vault_exists is True
    assert summary.projection_exists is True
    assert summary.model_exists is False
    assert summary.stats is not None and summary.stats.n_lessons == 1
    assert calls == [first]


def test_ops_refresh_and_train_share_one_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _context(tmp_path, "A"), _context(tmp_path, "B")
    calls = _flipping_resolver(monkeypatch, first, second)
    seen: list[ActiveVaultContext] = []
    monkeypatch.setattr(
        server,
        "_sync_vault_import",
        lambda context: seen.append(context)
        or server.VaultImportResponse(message="ok", n_lessons=1, output_path="A", topics=["topic"]),
    )
    monkeypatch.setattr(
        server,
        "_train_topic_for_context",
        lambda context: seen.append(context)
        or server.TrainResponse(message="ok", n_lessons=1, topics=["topic"]),
    )

    response = server.ops_refresh(train=True)

    assert response.train_result is not None
    assert seen == [first, first]
    assert calls == [first]
