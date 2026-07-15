from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import unicodedata
from typing import Any, Literal, Protocol, cast

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity

from lele_manager.ml.features import LessonFeatureExtractor


DEFAULT_MIN_SCORE = 0.85


class _SupportsToCsr(Protocol):
    def tocsr(self) -> sparse.csr_matrix:
        ...


@dataclass(frozen=True, slots=True)
class DuplicatePair:
    left_id: str
    right_id: str
    left_position: int
    right_position: int
    kind: Literal["exact", "near"]
    score: float
    reasons: tuple[str, ...]
    shared_tags: tuple[str, ...]
    left_path: str | None = None
    right_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        result["shared_tags"] = list(self.shared_tags)
        return result


@dataclass(frozen=True, slots=True)
class DuplicateReport:
    lessons_analyzed: int
    total_pairs: int
    exact_pairs: int
    near_pairs: int
    min_score: float
    exact_only: bool
    pairs: tuple[DuplicatePair, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "lessons_analyzed": self.lessons_analyzed,
            "total_pairs": self.total_pairs,
            "exact_pairs": self.exact_pairs,
            "near_pairs": self.near_pairs,
            "min_score": self.min_score,
            "exact_only": self.exact_only,
            "pairs": [pair.to_dict() for pair in self.pairs],
        }


def _value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _normalize_short(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFC", _value(value)).strip().split()).casefold()


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFC", _value(value)).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _tags(value: Any) -> dict[str, str]:
    if not isinstance(value, (list, tuple, set)):
        return {}
    displays = (
        " ".join(unicodedata.normalize("NFC", _value(tag)).strip().split())
        for tag in value
    )
    normalized: dict[str, str] = {}
    for display in sorted(filter(None, displays), key=lambda item: (item.casefold(), item)):
        normalized.setdefault(display.casefold(), display)
    return normalized


def _metadata_reasons(left: pd.Series, right: pd.Series) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    for field, reason in (
        ("title", "same_title"),
        ("topic", "same_topic"),
        ("source", "same_source"),
        ("date", "same_date"),
    ):
        left_value = _normalize_short(left.get(field))
        if left_value and left_value == _normalize_short(right.get(field)):
            reasons.append(reason)

    left_tags = _tags(left.get("tags"))
    right_tags = _tags(right.get("tags"))
    shared_keys = sorted(left_tags.keys() & right_tags.keys())
    shared = [left_tags[key] for key in shared_keys]
    if shared:
        reasons.append("shared_tags")
    return reasons, shared


def _stable_metadata_equal(left: pd.Series, right: pd.Series) -> bool:
    fields = ("title", "topic", "source", "date", "importance")
    values_left = tuple(_normalize_short(left.get(field)) for field in fields)
    values_right = tuple(_normalize_short(right.get(field)) for field in fields)
    return values_left == values_right and sorted(_tags(left.get("tags"))) == sorted(_tags(right.get("tags")))


def _has_significant_metadata(lesson: pd.Series) -> bool:
    fields = ("title", "topic", "source", "date", "importance")
    return any(_normalize_short(lesson.get(field)) for field in fields) or bool(_tags(lesson.get("tags")))


def _sort_key(pair: DuplicatePair) -> tuple[Any, ...]:
    return (
        0 if pair.kind == "exact" else 1,
        -pair.score,
        pair.left_id,
        pair.right_id,
        pair.left_position,
        pair.right_position,
    )


def find_duplicates(
    lessons: pd.DataFrame,
    *,
    transformer: LessonFeatureExtractor | None = None,
    feature_matrix: sparse.spmatrix | np.ndarray | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
    exact_only: bool = False,
    limit: int | None = None,
) -> DuplicateReport:
    """Find exact and semantic duplicate candidates without mutating inputs."""
    if not math.isfinite(min_score) or not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0 and 1")
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    if not exact_only and len(lessons) > 1 and transformer is None and feature_matrix is None:
        raise ValueError("a fitted transformer or feature matrix is required for near-duplicate detection")

    df = lessons.reset_index(drop=True)
    if not exact_only and feature_matrix is not None and feature_matrix.shape[0] != len(df):
        raise ValueError("feature matrix must have the same number of rows as lessons")
    scores: np.ndarray | None = None
    if not exact_only and len(df) > 1:
        matrix_input = feature_matrix
        if matrix_input is None:
            assert transformer is not None
            matrix_input = transformer.transform(df)

        if isinstance(matrix_input, np.ndarray):
            matrix = sparse.csr_matrix(matrix_input)
        else:
            matrix = cast(_SupportsToCsr, matrix_input).tocsr()

        scores = cosine_similarity(matrix)

    pairs: list[DuplicatePair] = []
    for left_pos in range(len(df)):
        left = df.iloc[left_pos]
        for right_pos in range(left_pos + 1, len(df)):
            right = df.iloc[right_pos]
            left_id = _value(left.get("id"))
            right_id = _value(right.get("id"))
            reasons, shared_tags = _metadata_reasons(left, right)

            exact_reasons: list[str] = []
            if left_id and left_id == right_id:
                exact_reasons.append("duplicate_id")
            left_text = _normalize_text(left.get("text"))
            text_equal = bool(left_text) and left_text == _normalize_text(right.get("text"))
            if text_equal:
                exact_reasons.append("exact_text")
                if _stable_metadata_equal(left, right) and (
                    _has_significant_metadata(left) or _has_significant_metadata(right)
                ):
                    exact_reasons.append("equivalent_metadata")

            if exact_reasons:
                kind: Literal["exact", "near"] = "exact"
                score = 1.0
                all_reasons = exact_reasons + reasons
            else:
                if exact_only:
                    continue
                assert scores is not None
                score = float(scores[left_pos, right_pos])
                if min_score > 0.0 and score < min_score:
                    continue
                kind = "near"
                all_reasons = reasons

            pairs.append(
                DuplicatePair(
                    left_id=left_id,
                    right_id=right_id,
                    left_position=left_pos,
                    right_position=right_pos,
                    kind=kind,
                    score=score,
                    reasons=tuple(all_reasons),
                    shared_tags=tuple(shared_tags),
                    left_path=_value(left.get("path")) or None,
                    right_path=_value(right.get("path")) or None,
                )
            )

    pairs.sort(key=_sort_key)
    exact_count = sum(pair.kind == "exact" for pair in pairs)
    near_count = len(pairs) - exact_count
    total_count = len(pairs)
    if limit is not None:
        pairs = pairs[:limit]
    return DuplicateReport(
        lessons_analyzed=len(df),
        total_pairs=total_count,
        exact_pairs=exact_count,
        near_pairs=near_count,
        min_score=min_score,
        exact_only=exact_only,
        pairs=tuple(pairs),
    )
