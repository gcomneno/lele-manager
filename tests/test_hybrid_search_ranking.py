from __future__ import annotations

import pytest

from lele_manager.core.hybrid_search import (
    HybridSearchDocument,
    rank_hybrid_documents,
)


def _doc(
    lesson_id: str,
    *,
    text: str = "",
    title: str | None = None,
    topic: str | None = None,
    tags: tuple[str, ...] = (),
    source: str | None = None,
) -> HybridSearchDocument:
    return HybridSearchDocument(
        lesson_id=lesson_id,
        text=text,
        title=title,
        topic=topic,
        tags=tags,
        source=source,
    )


def test_exact_title_match_is_protected_from_semantic_only_candidate() -> None:
    results = rank_hybrid_documents(
        [
            _doc("exact", title="Python retries"),
            _doc("semantic", text="Resilient distributed operations"),
        ],
        query="python retries",
        semantic_scores={"semantic": 1.0},
    )

    assert [result.lesson_id for result in results] == ["exact", "semantic"]
    assert results[0].protected_lexical_tier == 2
    assert [reason.code for reason in results[0].reasons] == [
        "exact-title-match"
    ]


def test_exact_phrase_match_is_protected_from_semantic_only_candidate() -> None:
    results = rank_hybrid_documents(
        [
            _doc("phrase", text="Always use idempotency keys for payment retries."),
            _doc("semantic", text="Safe repeated operations"),
        ],
        query="idempotency keys",
        semantic_scores={"semantic": 1.0},
    )

    assert [result.lesson_id for result in results] == ["phrase", "semantic"]
    assert results[0].protected_lexical_tier == 1
    assert results[0].reasons[0].code == "exact-phrase-match"
    assert results[0].reasons[0].value == "text"


def test_phrase_protection_requires_word_boundaries() -> None:
    results = rank_hybrid_documents(
        [
            _doc("nosql", text="NoSQL databases are useful here."),
            _doc("semantic", text="Relational database guidance."),
        ],
        query="sql",
        semantic_scores={"semantic": 1.0},
    )

    assert [result.lesson_id for result in results] == [
        "semantic",
        "nosql",
    ]
    assert results[1].protected_lexical_tier == 0
    assert [reason.code for reason in results[1].reasons] == [
        "text-match"
    ]


def test_legacy_substring_match_remains_retrievable_without_phrase_protection() -> None:
    results = rank_hybrid_documents(
        [_doc("banana", text="banana")],
        query="an",
    )

    assert [result.lesson_id for result in results] == ["banana"]
    assert results[0].protected_lexical_tier == 0
    assert [reason.code for reason in results[0].reasons] == [
        "text-match"
    ]


def test_semantic_only_candidate_can_be_retrieved_without_literal_query() -> None:
    results = rank_hybrid_documents(
        [_doc("semantic", text="Retry operations must be safe to repeat.")],
        query="idempotency",
        semantic_scores={"semantic": 0.81},
    )

    assert [result.lesson_id for result in results] == ["semantic"]
    assert results[0].protected_lexical_tier == 0
    assert [reason.code for reason in results[0].reasons] == [
        "semantic-similarity"
    ]
    assert results[0].reasons[0].value == pytest.approx(0.81)


def test_query_metadata_matches_are_explainable_relevance_not_filters() -> None:
    results = rank_hybrid_documents(
        [
            _doc(
                "metadata",
                topic="python",
                tags=("pytest", "testing"),
                source="internal python notes",
            )
        ],
        query="python pytest",
    )

    assert [result.lesson_id for result in results] == ["metadata"]
    assert [reason.code for reason in results[0].reasons] == [
        "topic-match",
        "tag-match",
        "source-match",
    ]
    assert results[0].reasons[1].value == "pytest"


def test_nonmatching_document_without_semantic_evidence_is_not_returned() -> None:
    results = rank_hybrid_documents(
        [_doc("unrelated", text="Git branching strategies")],
        query="python retries",
    )

    assert results == []


def test_ranking_is_deterministic_across_input_order() -> None:
    documents = [
        _doc("b", text="python"),
        _doc("a", text="python"),
        _doc("c", text="python"),
    ]

    forward = rank_hybrid_documents(documents, query="python")
    reverse = rank_hybrid_documents(list(reversed(documents)), query="python")

    assert [result.lesson_id for result in forward] == ["a", "b", "c"]
    assert forward == reverse


def test_limit_is_applied_after_ranking() -> None:
    results = rank_hybrid_documents(
        [
            _doc("semantic", text="unrelated"),
            _doc("phrase", text="python retries are useful"),
            _doc("exact", title="python retries"),
        ],
        query="python retries",
        semantic_scores={"semantic": 1.0},
        limit=2,
    )

    assert [result.lesson_id for result in results] == ["exact", "phrase"]


@pytest.mark.parametrize("score", [-0.01, 1.01, float("inf"), float("nan")])
def test_invalid_semantic_score_fails_explicitly(score: float) -> None:
    with pytest.raises(ValueError, match="semantic score"):
        rank_hybrid_documents(
            [_doc("candidate", text="anything")],
            query="python",
            semantic_scores={"candidate": score},
        )


def test_zero_semantic_score_does_not_create_fake_explanation() -> None:
    results = rank_hybrid_documents(
        [_doc("candidate", topic="python")],
        query="python",
        semantic_scores={"candidate": 0.0},
    )

    assert [reason.code for reason in results[0].reasons] == ["topic-match"]


def test_empty_query_is_not_ranked_as_semantic_search() -> None:
    with pytest.raises(ValueError, match="non-empty query"):
        rank_hybrid_documents(
            [_doc("candidate", text="python")],
            query="   ",
            semantic_scores={"candidate": 1.0},
        )
