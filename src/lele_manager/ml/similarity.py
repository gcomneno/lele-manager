from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline

from .features import LessonFeatureExtractor

@dataclass
class LessonSimilarityResult:
    lesson_id: str
    score: float

class LessonSimilarityIndex:
    """
    Indice di similarità basato sulle stesse feature usate per il topic model.

    Puoi costruirlo:
      - da un LessonFeatureExtractor fittato
      - oppure passando una Pipeline e usando lo step 'features'
    """

    def __init__(
        self,
        transformer: LessonFeatureExtractor,
        lesson_ids: np.ndarray,
        feature_matrix: sparse.csr_matrix,
    ) -> None:
        self.transformer = transformer
        self.lesson_ids = lesson_ids
        self.feature_matrix = feature_matrix

    # --- Costruttori di comodo ---

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        transformer: LessonFeatureExtractor,
        id_column: str = "id",
    ) -> "LessonSimilarityIndex":
        if id_column in df.columns:
            ids = df[id_column].astype(str).to_numpy()
        else:
            ids = df.index.astype(str).to_numpy()

        feature_matrix = transformer.transform(df)
        return cls(
            transformer=transformer,
            lesson_ids=ids,
            feature_matrix=feature_matrix,
        )

    @classmethod
    def from_topic_pipeline(
        cls,
        df: pd.DataFrame,
        pipeline: Pipeline,
        id_column: str = "id",
    ) -> "LessonSimilarityIndex":
        """
        Usa direttamente una Pipeline addestrata di tipo:
        [features] -> [clf]
        """
        try:
            transformer: LessonFeatureExtractor = pipeline.named_steps["features"]  # type: ignore[assignment]
        except KeyError:
            raise KeyError(
                "Pipeline must have a 'features' step of type LessonFeatureExtractor."
            )

        return cls.from_dataframe(df=df, transformer=transformer, id_column=id_column)

    # --- Query ---
    def most_similar(
        self,
        query_text: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[LessonSimilarityResult]:
        """
        Restituisce fino a `top_k` lesson simili al testo dato.
        """
        query_df = pd.DataFrame({"text": [query_text]})
        query_vec = self.transformer.transform(query_df)

        scores = cosine_similarity(query_vec, self.feature_matrix).ravel()
        if min_score > 0.0:
            mask = scores >= min_score
        else:
            mask = np.ones_like(scores, dtype=bool)

        # Ordina per score desc
        idx_sorted = np.argsort(scores[mask])[::-1]
        scores_filtered = scores[mask][idx_sorted]

        lesson_ids_filtered = self.lesson_ids[mask][idx_sorted]

        results: List[LessonSimilarityResult] = []
        for lesson_id, score in zip(lesson_ids_filtered[:top_k], scores_filtered[:top_k]):
            results.append(
                LessonSimilarityResult(
                    lesson_id=str(lesson_id),
                    score=float(score),
                )
            )
        return results
