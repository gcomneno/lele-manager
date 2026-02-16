from __future__ import annotations

from typing import List, Optional

import pandas as pd

from lele_manager.core.ranking import SimilarityRankingConfig
from lele_manager.ml.features import LessonFeatureExtractor
from lele_manager.ml.similarity import LessonSimilarityResult
from lele_manager.ml.similarity_backend import SimilarityBackend, TfidfSimilarityBackend


# Similarity Service Boundary (SSOT for orchestration semantics).
# IMPORTANT: keep backward-compatible positional signature.


def similar_by_text(
    df: pd.DataFrame,
    query_text: str,
    transformer: LessonFeatureExtractor,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
    ranking: Optional[SimilarityRankingConfig] = None,
    backend: SimilarityBackend | None = None,
) -> List[LessonSimilarityResult]:
    """
    Free-text similarity orchestration.

    Must remain identical to the underlying engine semantics (defaults, determinism, ordering).
    """
    if ranking is None:
        ranking = SimilarityRankingConfig()
    if backend is None:
        backend = TfidfSimilarityBackend()

    return backend.most_similar(
        df=df,
        query_text=query_text,
        transformer=transformer,
        top_k=top_k if top_k is not None else ranking.top_k_default,
        min_score=min_score if min_score is not None else ranking.min_score_default,
        ranking=ranking,
    )


def similar_by_lesson_id(
    df: pd.DataFrame,
    lesson_id: str,
    transformer: LessonFeatureExtractor,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
    ranking: Optional[SimilarityRankingConfig] = None,
    backend: SimilarityBackend | None = None,
) -> List[LessonSimilarityResult]:
    """Lesson-id similarity orchestration: extracts query text and delegates.

    IMPORTANT: must remain equivalent to the baseline engine (self-match included).
    """
    if ranking is None:
        ranking = SimilarityRankingConfig()
    if "id" not in df.columns:
        raise KeyError("Expected 'id' column in DataFrame.")
    if "text" not in df.columns:
        raise KeyError("Expected \text column in DataFrame.")

    row = df[df["id"].astype(str) == str(lesson_id)]
    if row.empty:
        raise ValueError(f"Lesson id not found: {lesson_id}")

    query_text = str(row.iloc[0]["text"])

    return similar_by_text(
        df,
        query_text,
        transformer,
        top_k=top_k,
        min_score=min_score,
        ranking=ranking,
        backend=backend,
    )
