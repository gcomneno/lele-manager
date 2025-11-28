from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

@dataclass
class TextFeatureConfig:
    """Config per le feature testuali di base."""
    ngram_range: Tuple[int, int] = (1, 2)
    max_features: int = 20_000
    min_df: int = 2
    strip_accents: str = "unicode"
    lowercase: bool = True

class LessonFeatureExtractor(BaseEstimator, TransformerMixin):
    """
    Trasforma un DataFrame di lesson in una matrice di feature:

    - TF-IDF sul campo `text`
    - Meta-feature numeriche:
      - lunghezza in caratteri
      - numero di parole
      - importance (se presente)
    """

    def __init__(
        self,
        config: Optional[TextFeatureConfig] = None,
        use_meta_features: bool = True,
    ) -> None:
        self.config = config or TextFeatureConfig()
        self.use_meta_features = use_meta_features

        self.vectorizer = TfidfVectorizer(
            ngram_range=self.config.ngram_range,
            max_features=self.config.max_features,
            min_df=self.config.min_df,
            strip_accents=self.config.strip_accents,
            lowercase=self.config.lowercase,
        )
        self._scaler: Optional[StandardScaler] = None

    # --- API scikit-learn ---
    def fit(self, X: pd.DataFrame, y=None):  # type: ignore[override]
        texts = self._get_text_series(X)

        # 1) Fit TF-IDF
        self.vectorizer.fit(texts)

        # 2) Fit scaler sulle meta-feature (se abilitate)
        if self.use_meta_features:
            meta = self._compute_meta_features(X, texts)
            self._scaler = StandardScaler()
            self._scaler.fit(meta)

        return self

    def transform(self, X: pd.DataFrame):  # type: ignore[override]
        texts = self._get_text_series(X)

        # 1) TF-IDF
        X_tfidf = self.vectorizer.transform(texts)

        if not self.use_meta_features:
            return X_tfidf

        # 2) Meta feature scalate
        if self._scaler is None:
            raise RuntimeError("LessonFeatureExtractor must be fitted before transform().")

        meta = self._compute_meta_features(X, texts)
        meta_scaled = self._scaler.transform(meta)

        # 3) Concat TF-IDF + meta
        return sparse.hstack([X_tfidf, meta_scaled], format="csr")

    # --- Helper interni ---
    @staticmethod
    def _get_text_series(X: pd.DataFrame) -> pd.Series:
        if "text" not in X.columns:
            raise KeyError("Expected column 'text' in input DataFrame.")
        return X["text"].fillna("").astype(str)

    @staticmethod
    def _compute_meta_features(
        X: pd.DataFrame,
        texts: pd.Series,
    ) -> np.ndarray:
        # Lunghezza in caratteri
        lengths = texts.str.len().to_numpy(dtype=float)[:, None]

        # Numero di parole (split su whitespace)
        word_counts = texts.str.split().str.len().to_numpy(dtype=float)[:, None]

        # Importance se presente, altrimenti zero
        if "importance" in X.columns:
            importance = (
                X["importance"]
                .fillna(0)
                .astype(float)
                .to_numpy()[:, None]
            )
        else:
            importance = np.zeros_like(lengths, dtype=float)

        # shape: (n_samples, 3)
        return np.hstack([lengths, word_counts, importance])
