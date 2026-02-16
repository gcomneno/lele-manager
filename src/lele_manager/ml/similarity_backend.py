from __future__ import annotations

from typing import Optional, Protocol

import pandas as pd

from lele_manager.core.ranking import SimilarityRankingConfig
from lele_manager.ml.features import LessonFeatureExtractor
from lele_manager.ml.similarity import LessonSimilarityIndex, LessonSimilarityResult


class SimilarityBackend(Protocol):
    """Backend interface for similarity computation (v2 abstraction)."""

    @property
    def name(self) -> str: ...

    def most_similar(
        self,
        *,
        df: pd.DataFrame,
        query_text: str,
        transformer: LessonFeatureExtractor,
        top_k: int,
        min_score: float,
        ranking: Optional[SimilarityRankingConfig] = None,
    ) -> list[LessonSimilarityResult]:
        ...

    def most_similar_by_lesson_id(
        self,
        *,
        df: pd.DataFrame,
        lesson_id: str,
        transformer: LessonFeatureExtractor,
        top_k: int,
        min_score: float,
        ranking: Optional[SimilarityRankingConfig] = None,
    ) -> list[LessonSimilarityResult]:
        ...


class TfidfSimilarityBackend:
    """Current backend: identical behavior to LessonSimilarityIndex (tf-idf)."""

    @property
    def name(self) -> str:
        return "tfidf"

    def most_similar(
        self,
        *,
        df: pd.DataFrame,
        query_text: str,
        transformer: LessonFeatureExtractor,
        top_k: int,
        min_score: float,
        ranking: Optional[SimilarityRankingConfig] = None,
    ) -> list[LessonSimilarityResult]:
        index = LessonSimilarityIndex.from_dataframe(df=df, transformer=transformer)
        return index.most_similar(
            query_text=query_text,
            top_k=top_k,
            min_score=min_score,
            ranking=ranking,
        )

    def most_similar_by_lesson_id(
        self,
        *,
        df: pd.DataFrame,
        lesson_id: str,
        transformer: LessonFeatureExtractor,
        top_k: int,
        min_score: float,
        ranking: Optional[SimilarityRankingConfig] = None,
    ) -> list[LessonSimilarityResult]:
        # reuse existing engine semantics, then remove self-match
        index = LessonSimilarityIndex.from_dataframe(df=df, transformer=transformer)

        row = df[df["id"].astype(str) == str(lesson_id)]
        if row.empty:
            raise ValueError(f"Lesson id not found: {lesson_id}")

        query_text = str(row.iloc[0]["text"])
        results = index.most_similar(
            query_text=query_text,
            top_k=top_k + 1,
            min_score=min_score,
            ranking=ranking,
        )
        filtered = [r for r in results if str(r.lesson_id) != str(lesson_id)]
        return filtered[:top_k]
