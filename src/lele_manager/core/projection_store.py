"""Backend-neutral port for the queryable lesson projection.

The types in this module are deliberately domain-facing: consumers see lesson
records, query criteria, aggregate statistics and a content generation.  They
do not see paths, JSONL, pandas, SQL, or backend transactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence, TypeAlias

LessonRecord: TypeAlias = Mapping[str, Any]


class ProjectionStoreError(Exception):
    """Base class for projection-store failures."""


class MalformedProjectionError(ProjectionStoreError):
    """The published projection cannot be decoded as valid lesson records."""


class DuplicateLessonIdError(ProjectionStoreError):
    """A snapshot contains more than one record with the same lesson ID."""


class LessonOrder(str, Enum):
    """Portable deterministic orderings supported by every backend."""

    SNAPSHOT = "snapshot"
    ID = "id"
    RELEVANCE = "relevance"
    CREATED_AT_DESC = "created_at_desc"


@dataclass(frozen=True)
class LessonQuery:
    """Filters for listing/searching the projection.

    Text matching is a case-insensitive substring of ``text``.  Empty filter
    sequences mean that no record can match.  A limit, when supplied, must be
    positive.
    """

    text: str | None = None
    topics: Sequence[str] | None = None
    sources: Sequence[str] | None = None
    tags: Sequence[str] | None = None
    importance_gte: int | None = None
    importance_lte: int | None = None
    order: LessonOrder = LessonOrder.SNAPSHOT
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be positive")


@dataclass(frozen=True)
class ProjectionStatistics:
    lesson_count: int
    topic_count: int
    unique_tag_count: int


class ProjectionSnapshot(Protocol):
    """One coherent, immutable view of a published generation."""

    @property
    def generation(self) -> str: ...

    @property
    def statistics(self) -> ProjectionStatistics: ...

    def get(self, lesson_id: str) -> LessonRecord | None: ...

    def list(self, query: LessonQuery = LessonQuery()) -> tuple[LessonRecord, ...]: ...


class ProjectionStore(Protocol):
    """Minimum common port implemented by projection backends.

    ``snapshot`` performs a coherent read. ``publish`` validates and atomically
    replaces the complete projection; it is not an authoring/upsert API.
    """

    def snapshot(self) -> ProjectionSnapshot: ...

    def publish(self, records: Sequence[LessonRecord]) -> ProjectionSnapshot: ...
