from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol, Sequence

from lele_manager.core.hybrid_search import (
    HybridSearchDocument,
    HybridSearchReason,
    rank_hybrid_documents,
)


class SemanticSearchUnavailable(Exception):
    """Supported degradation: optional local semantic retrieval is unavailable."""


class SemanticSearchProvider(Protocol):
    def scores_for_query(
        self,
        documents: Sequence[HybridSearchDocument],
        query: str,
    ) -> Mapping[str, float]:
        ...


@dataclass(frozen=True, slots=True)
class HybridSearchRecord:
    lesson_id: str
    text: str = ""
    title: str | None = None
    topic: str | None = None
    source: str | None = None
    importance: int | None = None
    tags: tuple[str, ...] = ()
    date: str | None = None
    created_at: str | None = None
    lifecycle: str = "active"
    freshness_review_needed: bool | None = None


@dataclass(frozen=True, slots=True)
class HybridSearchFilters:
    topic_in: tuple[str, ...] | None = None
    source_in: tuple[str, ...] | None = None
    importance_gte: int | None = None
    importance_lte: int | None = None
    lifecycle_in: tuple[str, ...] | None = None
    freshness_review_needed: bool | None = None


@dataclass(frozen=True, slots=True)
class HybridSearchRequest:
    query: str | None = None
    filters: HybridSearchFilters = HybridSearchFilters()
    limit: int = 50


@dataclass(frozen=True, slots=True)
class HybridSearchItem:
    record: HybridSearchRecord
    rank: int
    hybrid_score: float | None
    reasons: tuple[HybridSearchReason, ...]


@dataclass(frozen=True, slots=True)
class HybridSearchOutcome:
    items: tuple[HybridSearchItem, ...]
    semantic_attempted: bool
    semantic_available: bool


def _normalized_scope(values: tuple[str, ...] | None) -> set[str] | None:
    if values is None:
        return None
    return {value.strip() for value in values if value.strip()}


def _effective_lifecycle_scope(values: tuple[str, ...] | None) -> set[str]:
    if values is None:
        return {"active"}
    return {value.strip() for value in values if value.strip()}


def _eligible(
    record: HybridSearchRecord,
    filters: HybridSearchFilters,
) -> bool:
    lifecycle_scope = _effective_lifecycle_scope(filters.lifecycle_in)
    if record.lifecycle not in lifecycle_scope:
        return False

    topic_scope = _normalized_scope(filters.topic_in)
    if topic_scope is not None and record.topic not in topic_scope:
        return False

    source_scope = _normalized_scope(filters.source_in)
    if source_scope is not None and record.source not in source_scope:
        return False

    if filters.importance_gte is not None:
        if record.importance is None or record.importance < filters.importance_gte:
            return False

    if filters.importance_lte is not None:
        if record.importance is None or record.importance > filters.importance_lte:
            return False

    if filters.freshness_review_needed is not None:
        if record.freshness_review_needed is not filters.freshness_review_needed:
            return False

    return True


def _document(record: HybridSearchRecord) -> HybridSearchDocument:
    return HybridSearchDocument(
        lesson_id=record.lesson_id,
        text=record.text,
        title=record.title,
        topic=record.topic,
        tags=record.tags,
        source=record.source,
    )


def _created_at_sort_value(value: str | None) -> float:
    if value is None:
        return float("-inf")

    normalized = value.strip()
    if not normalized:
        return float("-inf")

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return float("-inf")

    try:
        return parsed.timestamp()
    except (OverflowError, OSError, ValueError):
        return float("-inf")


def _browse_sort_key(record: HybridSearchRecord) -> tuple[float, float, str]:
    importance = (
        float(record.importance)
        if record.importance is not None
        else float("-inf")
    )
    created_at = _created_at_sort_value(record.created_at)
    return (-importance, -created_at, record.lesson_id)


def _filtered_records(
    records: Sequence[HybridSearchRecord],
    filters: HybridSearchFilters,
) -> list[HybridSearchRecord]:
    return [record for record in records if _eligible(record, filters)]


def search_hybrid(
    records: Sequence[HybridSearchRecord],
    request: HybridSearchRequest,
    *,
    semantic_provider: SemanticSearchProvider | None = None,
) -> HybridSearchOutcome:
    """Execute maintained eligibility + hybrid retrieval semantics.

    Explicit filters establish eligibility before any semantic retrieval.

    With no non-empty query this remains a deterministic filtered browse using
    the legacy maintained ordering: importance DESC, created_at DESC, id ASC.

    With a query, lexical/metadata evidence comes from the pure core ranker and
    optional semantic evidence is obtained only for already eligible records.
    """

    if request.limit < 1:
        raise ValueError("limit must be >= 1")

    eligible = _filtered_records(records, request.filters)
    query = (request.query or "").strip()

    if not query:
        ordered = sorted(eligible, key=_browse_sort_key)[: request.limit]
        return HybridSearchOutcome(
            items=tuple(
                HybridSearchItem(
                    record=record,
                    rank=index,
                    hybrid_score=None,
                    reasons=(),
                )
                for index, record in enumerate(ordered, start=1)
            ),
            semantic_attempted=False,
            semantic_available=False,
        )

    documents = [_document(record) for record in eligible]
    by_id = {record.lesson_id: record for record in eligible}

    semantic_attempted = semantic_provider is not None
    semantic_available = False
    semantic_scores: Mapping[str, float] = {}

    if semantic_provider is not None and documents:
        try:
            semantic_scores = semantic_provider.scores_for_query(
                documents,
                query,
            )
        except SemanticSearchUnavailable:
            semantic_scores = {}
        else:
            semantic_available = True

    ranked = rank_hybrid_documents(
        documents,
        query=query,
        semantic_scores=semantic_scores,
        limit=request.limit,
    )

    return HybridSearchOutcome(
        items=tuple(
            HybridSearchItem(
                record=by_id[result.lesson_id],
                rank=index,
                hybrid_score=result.score,
                reasons=result.reasons,
            )
            for index, result in enumerate(ranked, start=1)
        ),
        semantic_attempted=semantic_attempted,
        semantic_available=semantic_available,
    )
