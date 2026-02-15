from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline

from .features import LessonFeatureExtractor
from lele_manager.core.ranking import SimilarityRankingConfig

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

        feature_matrix = sparse.csr_matrix(transformer.transform(df))
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

    def most_similar_with_ranking(
        self,
        query_text: str,
        *,
        ranking: SimilarityRankingConfig,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[LessonSimilarityResult]:
        """
        Entry-point interna per usare RankingConfig senza cambiare semantica
        o default della API pubblica `most_similar`.

        #34: non è usata dal server/CLI (nessun behavior change).
        """
        if top_k is None:
            top_k = ranking.top_k_default
        if min_score is None:
            min_score = ranking.min_score_default
        return self.most_similar(
            query_text=query_text,
            top_k=top_k,
            min_score=min_score,
            ranking=ranking,
        )

    # --- Query ---
    def most_similar(
        self,
        query_text: str,
        top_k: int = 5,
        min_score: float = 0.0,
        ranking: Optional[SimilarityRankingConfig] = None,
    ) -> List[LessonSimilarityResult]:
        """
        Restituisce fino a `top_k` lesson simili al testo dato.
        """
        if ranking is None:
            ranking = SimilarityRankingConfig()

        query_df = pd.DataFrame({"text": [query_text]})
        # Ensure stable typing + expected format for sklearn
        query_vec = sparse.csr_matrix(self.transformer.transform(query_df))

        scores = cosine_similarity(query_vec, self.feature_matrix).ravel()
        if min_score > 0.0:
            mask = scores >= min_score
        else:
            mask = np.ones_like(scores, dtype=bool)

        # Deterministic ranking:
        # 1) score DESC
        # 2) lesson_id ASC (tie-breaker)
        scores_m = scores[mask]
        lesson_ids_m = self.lesson_ids[mask].astype(str)
        order = np.lexsort((lesson_ids_m, -scores_m))
        scores_filtered = scores_m[order]
        lesson_ids_filtered = lesson_ids_m[order]

        results: List[LessonSimilarityResult] = []
        for lesson_id, score in zip(lesson_ids_filtered[:top_k], scores_filtered[:top_k]):
            results.append(
                LessonSimilarityResult(
                    lesson_id=str(lesson_id),
                    score=float(score),
                )
            )
        return results
