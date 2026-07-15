from __future__ import annotations

from dataclasses import dataclass

from typing import Optional, Protocol

import numpy as np
import pandas as pd
from scipy import sparse

from lele_manager.core.ranking import SimilarityRankingConfig
from lele_manager.ml.features import LessonFeatureExtractor
from lele_manager.ml.similarity import LessonSimilarityIndex, LessonSimilarityResult


class _SvdTransformer(Protocol):
    def transform(self, matrix: sparse.spmatrix) -> np.ndarray:
        ...


# --------------------------
# Internals: renamed classes for VSCode/Pylance sanity
# --------------------------
@dataclass(frozen=True)
class _LsaCacheKey_Internal:
    """
    In-process cache key (determinism guardrails).

    - id(df) + id(transformer) + shape
    - future: optional minimal fingerprint/hash
    """
    df_id: int
    transformer_id: int
    n_rows: int
    n_cols: int


@dataclass
class _LsaIndexCache_Internal:
    lesson_ids: np.ndarray
    x_dense: np.ndarray
    svd: _SvdTransformer


class _TfidfLsaBackend_Internal:
    """
    Backend LSA con guardrails interni:
    - determinismo
    - n_components validation
    - cache-key robusta (PoC)
    """

    def __init__(self, *, n_components: int = 128, random_state: int = 0) -> None:
        self._n_components = int(n_components)
        self._random_state = int(random_state)
        self._cache: dict[_LsaCacheKey_Internal, _LsaIndexCache_Internal] = {}

    @property
    def name(self) -> str:
        return "lsa-guardrails"

    def _build_or_get_index(self, *, df: pd.DataFrame, transformer: LessonFeatureExtractor) -> _LsaIndexCache_Internal:
        key = _LsaCacheKey_Internal(
            df_id=id(df),
            transformer_id=id(transformer),
            n_rows=int(df.shape[0]),
            n_cols=int(df.shape[1]),
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        from sklearn.decomposition import TruncatedSVD

        # ids
        if "id" in df.columns:
            lesson_ids = df["id"].astype(str).to_numpy()
        else:
            lesson_ids = df.index.astype(str).to_numpy()

        x = sparse.csr_matrix(transformer.transform(df))

        # Guardrail n_components
        n_samples, n_features = x.shape
        max_allowed = max(0, min(n_samples - 1, n_features - 1))
        n_components = min(self._n_components, max_allowed)
        if n_components < 2:
            raise ValueError(
                f"LSA backend requires n_components >=2; got {n_components} "
                f"(requested={self._n_components}, n_samples={n_samples}, n_features={n_features})"
            )

        svd = TruncatedSVD(n_components=n_components, random_state=self._random_state)
        x_dense = svd.fit_transform(x)
        cache = _LsaIndexCache_Internal(lesson_ids=lesson_ids, x_dense=np.asarray(x_dense), svd=svd)
        self._cache[key] = cache
        return cache

# --------------------------
# Alias pubblico pulito, senza V2
# --------------------------
TfidfLsaBackendGuardrails = _TfidfLsaBackend_Internal


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


@dataclass(frozen=True)
class _LsaCacheKey:
    """
    In-process cache key.

    Note: this is intentionally process-local and keyed on object identity + shape.
    Determinism is guaranteed by fixed random_state and deterministic ranking.
    """

    df_id: int
    transformer_id: int
    n_rows: int
    n_cols: int


@dataclass
class _LsaIndexCache:
    lesson_ids: np.ndarray
    x_dense: np.ndarray
    # store fitted svd so we can transform query vectors consistently
    svd: _SvdTransformer


class TfidfLsaSimilarityBackend:
    """
    Experimental backend: TF-IDF features -> TruncatedSVD (LSA) -> cosine similarity.

    Opt-in only (service default remains TF-IDF).
    """

    def __init__(self, *, n_components: int = 128, random_state: int = 0) -> None:
        self._n_components = int(n_components)
        self._random_state = int(random_state)
        self._cache: dict[_LsaCacheKey, _LsaIndexCache] = {}

    @property
    def name(self) -> str:
        return "lsa"

    def _build_or_get_index(
        self, *, df: pd.DataFrame, transformer: LessonFeatureExtractor
    ) -> _LsaIndexCache:
        key = _LsaCacheKey(
            df_id=id(df),
            transformer_id=id(transformer),
            n_rows=int(df.shape[0]),
            n_cols=int(df.shape[1]),
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        from sklearn.decomposition import TruncatedSVD

        # ids are derived exactly like LessonSimilarityIndex.from_dataframe
        if "id" in df.columns:
            lesson_ids = df["id"].astype(str).to_numpy()
        else:
            lesson_ids = df.index.astype(str).to_numpy()

        x = sparse.csr_matrix(transformer.transform(df))

        # Guardrails: TruncatedSVD requires 1 < n_components < min(n_samples, n_features)
        n_samples = int(x.shape[0])
        n_features = int(x.shape[1])
        max_allowed = max(0, min(n_samples - 1, n_features - 1))
        n_components = min(self._n_components, max_allowed)
        if n_components < 2:
            raise ValueError(
                f"LSA backend requires at least 2 components; "
                f"got n_components={n_components} (requested={self._n_components}, "
                f"n_samples={n_samples}, n_features={n_features})."
            )

        svd = TruncatedSVD(n_components=n_components, random_state=self._random_state)
        x_dense = svd.fit_transform(x)
        cache = _LsaIndexCache(lesson_ids=lesson_ids, x_dense=np.asarray(x_dense), svd=svd)
        self._cache[key] = cache
        return cache

    @staticmethod
    def _cosine_1_to_many(*, q: np.ndarray, x: np.ndarray) -> np.ndarray:
        qn = np.linalg.norm(q)
        xn = np.linalg.norm(x, axis=1)
        denom = (qn * xn)
        denom = np.where(denom == 0.0, 1.0, denom)
        return (x @ q) / denom

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
        if ranking is None:
            ranking = SimilarityRankingConfig()


        cache = self._build_or_get_index(df=df, transformer=transformer)
        query_df = pd.DataFrame({"text": [query_text]})
        q = sparse.csr_matrix(transformer.transform(query_df))
        q_dense = np.asarray(cache.svd.transform(q)).ravel()

        scores = self._cosine_1_to_many(q=q_dense, x=cache.x_dense).ravel()
        if min_score > 0.0:
            mask = scores >= float(min_score)
        else:
            mask = np.ones_like(scores, dtype=bool)

        scores_m = scores[mask]
        lesson_ids_m = cache.lesson_ids[mask].astype(str)
        order = np.lexsort((lesson_ids_m, -scores_m))
        scores_sorted = scores_m[order]
        lesson_ids_sorted = lesson_ids_m[order]

        results: list[LessonSimilarityResult] = []
        for lesson_id, score in zip(lesson_ids_sorted[:top_k], scores_sorted[:top_k]):
            results.append(LessonSimilarityResult(lesson_id=str(lesson_id), score=float(score)))
        return results

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
        row = df[df["id"].astype(str) == str(lesson_id)]
        if row.empty:
            raise ValueError(f"Lesson id not found: {lesson_id}")
        query_text = str(row.iloc[0]["text"])
        results = self.most_similar(
            df=df,
            query_text=query_text,
            transformer=transformer,
            top_k=top_k + 1,
            min_score=min_score,
            ranking=ranking,
        )
        filtered = [r for r in results if str(r.lesson_id) != str(lesson_id)]
        return filtered[:top_k]


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
