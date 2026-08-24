from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Literal, Mapping, Sequence


HybridSearchReasonCode = Literal[
    "exact-title-match",
    "exact-phrase-match",
    "title-match",
    "text-match",
    "topic-match",
    "tag-match",
    "source-match",
    "semantic-similarity",
]


@dataclass(frozen=True, slots=True)
class HybridSearchDocument:
    lesson_id: str
    text: str = ""
    title: str | None = None
    topic: str | None = None
    tags: tuple[str, ...] = ()
    source: str | None = None


@dataclass(frozen=True, slots=True)
class HybridSearchReason:
    code: HybridSearchReasonCode
    value: str | float | int | None = None


@dataclass(frozen=True, slots=True)
class HybridSearchResult:
    lesson_id: str
    score: float
    protected_lexical_tier: int
    reasons: tuple[HybridSearchReason, ...]


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.casefold().split())


def _tokens(value: str | None) -> frozenset[str]:
    return frozenset(_WORD_RE.findall(_normalize(value)))


def _contains_phrase(value: str, phrase: str) -> bool:
    if not value or not phrase:
        return False

    pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"
    return re.search(pattern, value, re.UNICODE) is not None


def _overlap_ratio(query_tokens: frozenset[str], value: str | None) -> float:
    if not query_tokens:
        return 0.0
    overlap = query_tokens & _tokens(value)
    return len(overlap) / len(query_tokens)


def _semantic_score(
    lesson_id: str,
    semantic_scores: Mapping[str, float],
) -> float | None:
    raw = semantic_scores.get(lesson_id)
    if raw is None:
        return None

    score = float(raw)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError(
            f"semantic score for {lesson_id!r} must be finite and between 0 and 1"
        )
    return score


def _rank_document(
    document: HybridSearchDocument,
    *,
    normalized_query: str,
    query_tokens: frozenset[str],
    semantic_scores: Mapping[str, float],
) -> HybridSearchResult | None:
    title = _normalize(document.title)
    text = _normalize(document.text)

    protected_tier = 0
    score = 0.0
    reasons: list[HybridSearchReason] = []

    if title and title == normalized_query:
        protected_tier = 2
        score += 1.0
        reasons.append(HybridSearchReason("exact-title-match"))
    else:
        phrase_fields: list[str] = []
        if _contains_phrase(title, normalized_query):
            phrase_fields.append("title")
        if _contains_phrase(text, normalized_query):
            phrase_fields.append("text")

        if phrase_fields:
            protected_tier = 1
            score += 0.9
            reasons.append(
                HybridSearchReason(
                    "exact-phrase-match",
                    ",".join(phrase_fields),
                )
            )
        else:
            title_overlap = _overlap_ratio(query_tokens, document.title)
            if title_overlap > 0.0:
                score += 0.60 * title_overlap
                reasons.append(
                    HybridSearchReason(
                        "title-match",
                        round(title_overlap, 6),
                    )
                )
            elif title and normalized_query in title:
                # Preserve legacy substring retrieval without granting
                # protected exact-phrase semantics inside a larger word.
                score += 0.30
                reasons.append(
                    HybridSearchReason(
                        "title-match",
                        0.5,
                    )
                )

            text_overlap = _overlap_ratio(query_tokens, document.text)
            if text_overlap > 0.0:
                score += 0.45 * text_overlap
                reasons.append(
                    HybridSearchReason(
                        "text-match",
                        round(text_overlap, 6),
                    )
                )
            elif text and normalized_query in text:
                # Legacy substring compatibility remains weak evidence only.
                score += 0.20
                reasons.append(
                    HybridSearchReason(
                        "text-match",
                        0.5,
                    )
                )

    topic_overlap = _overlap_ratio(query_tokens, document.topic)
    if topic_overlap > 0.0:
        score += 0.20 * topic_overlap
        reasons.append(
            HybridSearchReason(
                "topic-match",
                round(topic_overlap, 6),
            )
        )

    matched_tags = tuple(
        sorted(
            tag
            for tag in document.tags
            if query_tokens & _tokens(tag)
        )
    )
    if matched_tags:
        tag_ratio = min(1.0, len(matched_tags) / max(1, len(query_tokens)))
        score += 0.20 * tag_ratio
        reasons.append(
            HybridSearchReason(
                "tag-match",
                ",".join(matched_tags),
            )
        )

    source_overlap = _overlap_ratio(query_tokens, document.source)
    if source_overlap > 0.0:
        score += 0.10 * source_overlap
        reasons.append(
            HybridSearchReason(
                "source-match",
                round(source_overlap, 6),
            )
        )

    semantic_score = _semantic_score(document.lesson_id, semantic_scores)
    if semantic_score is not None and semantic_score > 0.0:
        score += 0.80 * semantic_score
        reasons.append(
            HybridSearchReason(
                "semantic-similarity",
                round(semantic_score, 6),
            )
        )

    if not reasons:
        return None

    return HybridSearchResult(
        lesson_id=document.lesson_id,
        score=round(score, 9),
        protected_lexical_tier=protected_tier,
        reasons=tuple(reasons),
    )


def rank_hybrid_documents(
    documents: Sequence[HybridSearchDocument],
    *,
    query: str,
    semantic_scores: Mapping[str, float] | None = None,
    limit: int | None = None,
) -> list[HybridSearchResult]:
    """Rank one non-empty retrieval query deterministically.

    Protected lexical tiers sort before the composed bounded relevance score:

    2. exact normalized title;
    1. exact normalized phrase in title/body;
    0. all other lexical, metadata and semantic evidence.

    The final tie-break is canonical lesson ID ascending.

    Empty-query filtered browse is intentionally outside this pure ranker and
    remains an application-workflow responsibility.
    """

    normalized_query = _normalize(query)
    if not normalized_query:
        raise ValueError("hybrid ranking requires a non-empty query")

    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1 when provided")

    scores = semantic_scores or {}
    query_tokens = _tokens(normalized_query)

    ranked = [
        result
        for document in documents
        if (
            result := _rank_document(
                document,
                normalized_query=normalized_query,
                query_tokens=query_tokens,
                semantic_scores=scores,
            )
        )
        is not None
    ]

    ranked.sort(
        key=lambda item: (
            -item.protected_lexical_tier,
            -item.score,
            item.lesson_id,
        )
    )

    if limit is not None:
        return ranked[:limit]
    return ranked
