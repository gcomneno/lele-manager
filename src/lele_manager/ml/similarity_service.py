from __future__ import annotations

from typing import Optional, List

import pandas as pd

from lele_manager.ml.features import LessonFeatureExtractor
from lele_manager.ml.similarity import LessonSimilarityIndex, LessonSimilarityResult
from lele_manager.core.ranking import SimilarityRankingConfig


# Similarity Service Boundary (wiring-only)
# DO NOT import legacy text_ml.py here.


def similar_by_text(
    df: pd.DataFrame,
    query_text: str,
    *,
    transformer: LessonFeatureExtractor,
    ranking: Optional[SimilarityRankingConfig] = None,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
) -> List[LessonSimilarityResult]:
    """
    Free-text similarity orchestration.

    Must remain identical to calling LessonSimilarityIndex.most_similar directly.
    """
    if ranking is None:
        ranking = SimilarityRankingConfig()

    index = LessonSimilarityIndex.from_dataframe(df=df, transformer=transformer)

    return index.most_similar(
        query_text=query_text,
        top_k=top_k if top_k is not None else ranking.top_k_default,
        min_score=min_score if min_score is not None else ranking.min_score_default,
        ranking=ranking,
    )


def similar_by_lesson_id(
    df: pd.DataFrame,
    lesson_id: str,
    *,
    transformer: LessonFeatureExtractor,
    ranking: Optional[SimilarityRankingConfig] = None,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
) -> List[LessonSimilarityResult]:
    """
    Lesson-id similarity orchestration: extracts query text and delegates.
    """
    if ranking is None:
        ranking = SimilarityRankingConfig()

    if "id" not in df.columns:
        raise KeyError("Expected 'id' column in DataFrame.")
    if "text" not in df.columns:
        raise KeyError("Expected 'text' column in DataFrame.")

    row = df[df["id"].astype(str) == str(lesson_id)]
    if row.empty:
        raise ValueError(f"Lesson id not found: {lesson_id}")

    query_text = str(row.iloc[0]["text"])

    index = LessonSimilarityIndex.from_dataframe(df=df, transformer=transformer)

    results = index.most_similar(
        query_text=query_text,
        top_k=top_k if top_k is not None else ranking.top_k_default,
        min_score=min_score if min_score is not None else ranking.min_score_default,
        ranking=ranking,
    )

    # IMPORTANT: no self-filtering here unless current API already filters it.
    return results
