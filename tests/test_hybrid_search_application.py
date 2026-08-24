from __future__ import annotations

from collections.abc import Sequence

import pytest

from lele_manager.application.hybrid_search import (
    HybridSearchFilters,
    HybridSearchRecord,
    HybridSearchRequest,
    SemanticSearchUnavailable,
    search_hybrid,
)
from lele_manager.core.hybrid_search import HybridSearchDocument


def _record(
    lesson_id: str,
    *,
    text: str = "",
    title: str | None = None,
    topic: str | None = None,
    source: str | None = None,
    importance: int | None = None,
    tags: tuple[str, ...] = (),
    created_at: str | None = None,
    lifecycle: str = "active",
    freshness_review_needed: bool | None = None,
) -> HybridSearchRecord:
    return HybridSearchRecord(
        lesson_id=lesson_id,
        text=text,
        title=title,
        topic=topic,
        source=source,
        importance=importance,
        tags=tags,
        created_at=created_at,
        lifecycle=lifecycle,
        freshness_review_needed=freshness_review_needed,
    )


class RecordingSemanticProvider:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[tuple[list[str], str]] = []

    def scores_for_query(
        self,
        documents: Sequence[HybridSearchDocument],
        query: str,
    ) -> dict[str, float]:
        self.calls.append(([document.lesson_id for document in documents], query))
        return self.scores


class UnavailableSemanticProvider:
    def scores_for_query(
        self,
        documents: Sequence[HybridSearchDocument],
        query: str,
    ) -> dict[str, float]:
        raise SemanticSearchUnavailable


class BrokenSemanticProvider:
    def scores_for_query(
        self,
        documents: Sequence[HybridSearchDocument],
        query: str,
    ) -> dict[str, float]:
        raise RuntimeError("semantic backend corrupt")


def test_lifecycle_defaults_to_active_before_ranking() -> None:
    outcome = search_hybrid(
        [
            _record("active", text="python retries"),
            _record(
                "deprecated",
                text="python retries",
                lifecycle="deprecated",
            ),
        ],
        HybridSearchRequest(query="python retries"),
    )

    assert [item.record.lesson_id for item in outcome.items] == ["active"]


def test_explicit_lifecycle_scope_is_composable() -> None:
    outcome = search_hybrid(
        [
            _record("active", text="python retries"),
            _record(
                "deprecated",
                text="python retries",
                lifecycle="deprecated",
            ),
        ],
        HybridSearchRequest(
            query="python retries",
            filters=HybridSearchFilters(
                lifecycle_in=("active", "deprecated"),
            ),
        ),
    )

    assert {item.record.lesson_id for item in outcome.items} == {
        "active",
        "deprecated",
    }


def test_empty_explicit_lifecycle_scope_returns_no_results() -> None:
    outcome = search_hybrid(
        [_record("active", text="python")],
        HybridSearchRequest(
            query="python",
            filters=HybridSearchFilters(lifecycle_in=()),
        ),
    )

    assert outcome.items == ()


def test_filters_run_before_semantic_provider() -> None:
    provider = RecordingSemanticProvider(
        {
            "allowed": 0.4,
            "filtered-topic": 1.0,
            "filtered-lifecycle": 1.0,
        }
    )

    outcome = search_hybrid(
        [
            _record(
                "allowed",
                text="safe repeated operations",
                topic="python",
            ),
            _record(
                "filtered-topic",
                text="safe repeated operations",
                topic="git",
            ),
            _record(
                "filtered-lifecycle",
                text="safe repeated operations",
                topic="python",
                lifecycle="archived",
            ),
        ],
        HybridSearchRequest(
            query="idempotency",
            filters=HybridSearchFilters(topic_in=("python",)),
        ),
        semantic_provider=provider,
    )

    assert provider.calls == [(["allowed"], "idempotency")]
    assert [item.record.lesson_id for item in outcome.items] == ["allowed"]


def test_semantic_only_result_can_enter_hybrid_results() -> None:
    provider = RecordingSemanticProvider({"semantic": 0.88})

    outcome = search_hybrid(
        [_record("semantic", text="safe repeated operations")],
        HybridSearchRequest(query="idempotency"),
        semantic_provider=provider,
    )

    assert [item.record.lesson_id for item in outcome.items] == ["semantic"]
    assert outcome.semantic_attempted is True
    assert outcome.semantic_available is True
    assert [reason.code for reason in outcome.items[0].reasons] == [
        "semantic-similarity"
    ]


def test_missing_semantic_model_degrades_to_lexical_search() -> None:
    outcome = search_hybrid(
        [
            _record("lexical", text="use idempotency keys"),
            _record("unrelated", text="git branching"),
        ],
        HybridSearchRequest(query="idempotency"),
        semantic_provider=UnavailableSemanticProvider(),
    )

    assert [item.record.lesson_id for item in outcome.items] == ["lexical"]
    assert outcome.semantic_attempted is True
    assert outcome.semantic_available is False
    assert all(
        reason.code != "semantic-similarity"
        for item in outcome.items
        for reason in item.reasons
    )


def test_unexpected_semantic_failure_is_not_silently_degraded() -> None:
    with pytest.raises(RuntimeError, match="semantic backend corrupt"):
        search_hybrid(
            [_record("lesson", text="python")],
            HybridSearchRequest(query="python"),
            semantic_provider=BrokenSemanticProvider(),
        )


def test_no_query_does_not_call_semantic_provider() -> None:
    provider = RecordingSemanticProvider({"a": 1.0})

    outcome = search_hybrid(
        [_record("a", text="python")],
        HybridSearchRequest(query="  "),
        semantic_provider=provider,
    )

    assert provider.calls == []
    assert outcome.semantic_attempted is False
    assert outcome.semantic_available is False


def test_no_query_preserves_legacy_deterministic_browse_order() -> None:
    outcome = search_hybrid(
        [
            _record(
                "a",
                importance=5,
                created_at="2025-01-01T00:00:00+00:00",
            ),
            _record(
                "b",
                importance=5,
                created_at="2026-01-01T00:00:00+00:00",
            ),
            _record(
                "c",
                importance=4,
                created_at="2027-01-01T00:00:00+00:00",
            ),
            _record("d", importance=5),
        ],
        HybridSearchRequest(),
    )

    assert [item.record.lesson_id for item in outcome.items] == [
        "b",
        "a",
        "d",
        "c",
    ]
    assert [item.rank for item in outcome.items] == [1, 2, 3, 4]
    assert all(item.hybrid_score is None for item in outcome.items)
    assert all(item.reasons == () for item in outcome.items)


def test_metadata_filters_do_not_become_relevance_reasons_by_themselves() -> None:
    outcome = search_hybrid(
        [
            _record(
                "lesson",
                text="retry operations",
                topic="python",
                source="notes",
                importance=5,
            )
        ],
        HybridSearchRequest(
            query="retry",
            filters=HybridSearchFilters(
                topic_in=("python",),
                source_in=("notes",),
                importance_gte=5,
            ),
        ),
    )

    codes = [reason.code for reason in outcome.items[0].reasons]
    assert codes == ["exact-phrase-match"]


def test_query_to_metadata_match_is_legitimate_ranking_evidence() -> None:
    outcome = search_hybrid(
        [
            _record(
                "lesson",
                topic="python",
                tags=("pytest",),
                source="internal notes",
            )
        ],
        HybridSearchRequest(query="python pytest"),
    )

    assert [reason.code for reason in outcome.items[0].reasons] == [
        "topic-match",
        "tag-match",
    ]


def test_importance_and_freshness_filters_remain_eligibility_constraints() -> None:
    outcome = search_hybrid(
        [
            _record(
                "wanted",
                text="python",
                importance=4,
                freshness_review_needed=True,
            ),
            _record(
                "low",
                text="python",
                importance=2,
                freshness_review_needed=True,
            ),
            _record(
                "fresh",
                text="python",
                importance=5,
                freshness_review_needed=False,
            ),
        ],
        HybridSearchRequest(
            query="python",
            filters=HybridSearchFilters(
                importance_gte=3,
                freshness_review_needed=True,
            ),
        ),
    )

    assert [item.record.lesson_id for item in outcome.items] == ["wanted"]


def test_limit_applies_after_hybrid_ranking() -> None:
    provider = RecordingSemanticProvider({"semantic": 1.0})

    outcome = search_hybrid(
        [
            _record("semantic", text="safe repeated operations"),
            _record("phrase", text="python retries are useful"),
            _record("exact", title="python retries"),
        ],
        HybridSearchRequest(query="python retries", limit=2),
        semantic_provider=provider,
    )

    assert [item.record.lesson_id for item in outcome.items] == [
        "exact",
        "phrase",
    ]


def test_result_order_is_stable_when_input_is_shuffled() -> None:
    records = [
        _record("c", text="python"),
        _record("a", text="python"),
        _record("b", text="python"),
    ]

    forward = search_hybrid(records, HybridSearchRequest(query="python"))
    reverse = search_hybrid(
        list(reversed(records)),
        HybridSearchRequest(query="python"),
    )

    assert [item.record.lesson_id for item in forward.items] == ["a", "b", "c"]
    assert forward == reverse


def test_invalid_limit_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="limit"):
        search_hybrid(
            [_record("a", text="python")],
            HybridSearchRequest(query="python", limit=0),
        )
