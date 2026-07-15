from __future__ import annotations

import json
import os
from pathlib import Path
from collections.abc import Callable

import pytest

from lele_manager.adapters import jsonl_projection_store as jsonl_adapter
from lele_manager.adapters.jsonl_projection_store import JsonlProjectionStore
from lele_manager.core.projection_store import (
    DuplicateLessonIdError,
    LessonOrder,
    LessonQuery,
    MalformedProjectionError,
    ProjectionStore,
)


@pytest.fixture(params=["jsonl"])
def store_factory(request: pytest.FixtureRequest) -> Callable[[Path], ProjectionStore]:
    assert request.param == "jsonl"
    return JsonlProjectionStore


def complete_records() -> list[dict[str, object]]:
    return [
        {
            "id": "writing/caffè-☕",
            "text": "Usa Unicode: perché è parte del contenuto.",
            "topic": "writing",
            "source": "note",
            "importance": 4,
            "tags": ["unicode", "caffè"],
            "created_at": "2025-02-01T10:00:00+00:00",
            "title": "Accenti",
            "date": "2025-02-01",
            "frontmatter": {"unknown_future_field": "preserved"},
        },
        {
            "id": "python/atomic-files",
            "text": "Replace files atomically",
            "topic": "python",
            "source": "book",
            "importance": 5,
            "tags": ["filesystem", "python"],
            "created_at": "2025-03-01T10:00:00Z",
        },
        {
            "id": "misc/minimal",
            "text": "Optional fields may be absent",
            "importance": None,
        },
    ]


def test_complete_optional_unicode_tags_and_canonical_ids(
    tmp_path: Path, store_factory: Callable[[Path], ProjectionStore]
) -> None:
    store = store_factory(tmp_path / "lessons.jsonl")
    published = store.publish(complete_records())

    assert published.statistics.lesson_count == 3
    assert published.statistics.topic_count == 2
    assert published.statistics.unique_tag_count == 4
    assert published.get("writing/caffè-☕") == complete_records()[0]
    assert published.get("missing") is None
    assert store.snapshot().get("misc/minimal") == complete_records()[2]


def test_filters_order_limits_and_returned_records_are_isolated(
    tmp_path: Path, store_factory: Callable[[Path], ProjectionStore]
) -> None:
    store = store_factory(tmp_path / "lessons.jsonl")
    snapshot = store.publish(complete_records())

    result = snapshot.list(
        LessonQuery(
            text="FILE",
            topics=["python"],
            sources=["book"],
            tags=["filesystem"],
            importance_gte=5,
            importance_lte=5,
            order=LessonOrder.RELEVANCE,
            limit=1,
        )
    )
    assert [row["id"] for row in result] == ["python/atomic-files"]
    assert [row["id"] for row in snapshot.list(LessonQuery(order=LessonOrder.ID, limit=2))] == [
        "misc/minimal",
        "python/atomic-files",
    ]
    assert snapshot.list(LessonQuery(topics=[])) == ()

    mutable_result = dict(snapshot.get("writing/caffè-☕") or {})
    mutable_result["text"] = "changed by caller"
    assert snapshot.get("writing/caffè-☕")["text"] != "changed by caller"  # type: ignore[index]


def test_contract_rejects_duplicate_publication_and_tracks_content_generation(
    tmp_path: Path, store_factory: Callable[[Path], ProjectionStore]
) -> None:
    store = store_factory(tmp_path / "lessons.jsonl")
    first = store.publish([{"id": "one", "text": "before"}])
    changed = store.publish([{"id": "one", "text": "after"}])
    assert changed.generation != first.generation
    with pytest.raises(DuplicateLessonIdError, match="one"):
        store.publish([{"id": "one"}, {"id": "one"}])


def test_serialization_and_generation_are_deterministic(tmp_path: Path) -> None:
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    records = complete_records()
    first = JsonlProjectionStore(first_path).publish(records)
    second = JsonlProjectionStore(second_path).publish(list(reversed(records)))

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.generation == second.generation
    assert "caffè-☕" in first_path.read_text(encoding="utf-8")

    same = JsonlProjectionStore(first_path).publish(complete_records())
    assert same.generation == first.generation
    changed_records = complete_records()
    changed_records[0]["text"] = "Changed"
    changed = JsonlProjectionStore(first_path).publish(changed_records)
    assert changed.generation != first.generation


def test_duplicate_ids_and_malformed_records_are_explicit(tmp_path: Path) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_text('{"id":"same"}\n{"id":"same"}\n', encoding="utf-8")
    with pytest.raises(DuplicateLessonIdError, match="same"):
        JsonlProjectionStore(path).snapshot()

    path.write_text('{"id":"ok"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(MalformedProjectionError, match="line 2"):
        JsonlProjectionStore(path).snapshot()

    path.write_text(json.dumps(["not", "an", "object"]) + "\n", encoding="utf-8")
    with pytest.raises(MalformedProjectionError, match="not an object"):
        JsonlProjectionStore(path).snapshot()


def test_atomic_replacement_keeps_existing_snapshot_coherent(tmp_path: Path) -> None:
    store = JsonlProjectionStore(tmp_path / "lessons.jsonl")
    old = store.publish([{"id": "old", "text": "old"}])
    new = store.publish([{"id": "new", "text": "new"}])

    assert old.get("old") is not None
    assert old.get("new") is None
    assert new.get("old") is None
    assert store.snapshot().get("new") is not None


def test_manual_snapshot_order_changes_generation(tmp_path: Path) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_text('{"id":"a"}\n{"id":"b"}\n', encoding="utf-8")
    first = JsonlProjectionStore(path).snapshot()
    path.write_text('{"id":"b"}\n{"id":"a"}\n', encoding="utf-8")
    second = JsonlProjectionStore(path).snapshot()
    assert [row["id"] for row in first.list()] == ["a", "b"]
    assert [row["id"] for row in second.list()] == ["b", "a"]
    assert first.generation != second.generation


def test_publish_preserves_existing_permissions(tmp_path: Path) -> None:
    path = tmp_path / "lessons.jsonl"
    path.write_text('{"id":"old"}\n', encoding="utf-8")
    os.chmod(path, 0o640)
    JsonlProjectionStore(path).publish([{"id": "new"}])
    assert path.stat().st_mode & 0o777 == 0o640


def test_failed_publication_retains_previous_readable_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "lessons.jsonl"
    store = JsonlProjectionStore(path)
    previous = store.publish([{"id": "old", "text": "still readable"}])

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("interrupted before replace")

    monkeypatch.setattr(jsonl_adapter.os, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        store.publish([{"id": "new", "text": "not published"}])

    current = store.snapshot()
    assert current.generation == previous.generation
    assert current.get("old") is not None
    assert current.get("new") is None
    assert list(tmp_path.glob(".lessons.jsonl.*.tmp")) == []
