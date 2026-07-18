from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from lele_manager.application.external_lessons import external_lessons_feed
from lele_manager.core.projection_store import (
    LessonOrder,
    LessonQuery,
    ProjectionStatistics,
)


class FakeSnapshot:
    generation = "generation-7"
    statistics = ProjectionStatistics(9, 2, 3)

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.queries: list[LessonQuery] = []

    def get(self, lesson_id: str) -> dict[str, Any] | None:
        return None

    def list(self, query: LessonQuery = LessonQuery()) -> tuple[dict[str, Any], ...]:
        self.queries.append(query)
        return tuple(self.records)


class FakeStore:
    def __init__(self, snapshot: FakeSnapshot) -> None:
        self.value = snapshot
        self.snapshot_calls = 0
        self.publish_calls = 0

    def snapshot(self) -> FakeSnapshot:
        self.snapshot_calls += 1
        return self.value

    def publish(self, records: object) -> FakeSnapshot:
        self.publish_calls += 1
        raise AssertionError("the external feed must be read-only")


def test_feed_has_exact_public_shape_and_uses_one_snapshot() -> None:
    source = {
        "id": 42,
        "text": "A lesson",
        "title": "Title",
        "topic": "python",
        "source": "notes",
        "importance": "4",
        "tags": ["z", "a", "z"],
        "date": "2026-01-02",
        "created_at": "2026-01-02T03:04:05Z",
        "frontmatter": {"secret": True},
        "frontmatter_hash": "internal",
        "path": "/internal/lesson.md",
        "unknown": "excluded",
    }
    original = deepcopy(source)
    snapshot = FakeSnapshot([source])
    store = FakeStore(snapshot)
    query = LessonQuery(order=LessonOrder.ID)

    feed = external_lessons_feed(store, query)

    assert asdict(feed) == {
        "schema_version": 1,
        "generation": "generation-7",
        "total_lessons": 9,
        "returned_lessons": 1,
        "lessons": [
            {
                "id": "42",
                "text": "A lesson",
                "title": "Title",
                "topic": "python",
                "source": "notes",
                "importance": 4,
                "tags": ["a", "z"],
                "date": "2026-01-02",
                "created_at": "2026-01-02T03:04:05Z",
            }
        ],
    }
    assert source == original
    assert store.snapshot_calls == 1
    assert store.publish_calls == 0
    assert snapshot.queries == [query]


def test_query_filters_and_id_order_are_passed_to_snapshot() -> None:
    snapshot = FakeSnapshot([])
    query = LessonQuery(
        text="needle",
        topics=["python", "git"],
        sources=["notes"],
        tags=["quiz", "review"],
        importance_gte=2,
        importance_lte=4,
        order=LessonOrder.ID,
        limit=8,
    )

    external_lessons_feed(FakeStore(snapshot), query)

    assert snapshot.queries == [query]
    assert snapshot.queries[0].order is LessonOrder.ID


def test_irregular_values_are_normalized_without_mutation() -> None:
    source = {
        "id": "lesson",
        "text": {"invalid": "structured"},
        "title": ["invalid"],
        "topic": 12,
        "source": None,
        "importance": True,
        "tags": ["b", "", None, 3, "a", "b", {"bad": True}, ["bad"], float("nan")],
        "date": float("inf"),
        "created_at": False,
    }
    original = deepcopy(source)

    lesson = external_lessons_feed(
        FakeStore(FakeSnapshot([source])), LessonQuery(order=LessonOrder.ID)
    ).lessons[0]

    assert asdict(lesson) == {
        "id": "lesson",
        "text": "",
        "title": None,
        "topic": "12",
        "source": None,
        "importance": None,
        "tags": ["3", "a", "b"],
        "date": None,
        "created_at": "False",
    }
    assert source == original


def test_importance_rejects_non_integral_and_invalid_values() -> None:
    records = [
        {"id": "a", "importance": 2.0},
        {"id": "b", "importance": "2.5"},
        {"id": "c", "importance": " 5 "},
    ]

    lessons = external_lessons_feed(
        FakeStore(FakeSnapshot(records)), LessonQuery(order=LessonOrder.ID)
    ).lessons

    assert [lesson.importance for lesson in lessons] == [2, None, 5]


def test_empty_dataset_returns_empty_feed() -> None:
    snapshot = FakeSnapshot([])
    snapshot.statistics = ProjectionStatistics(0, 0, 0)

    feed = external_lessons_feed(FakeStore(snapshot), LessonQuery(order=LessonOrder.ID))

    assert feed.total_lessons == 0
    assert feed.returned_lessons == 0
    assert feed.lessons == []
