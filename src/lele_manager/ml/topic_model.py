from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .features import LessonFeatureExtractor, TextFeatureConfig


@dataclass
class TopicModelConfig:
    """Config della pipeline di classificazione topic."""
    # ⚠️ Importante: usare default_factory per i dataclass mutabili
    text_features: TextFeatureConfig = field(default_factory=TextFeatureConfig)
    C: float = 4.0
    max_iter: int = 1_000
    use_meta_features: bool = True


def build_topic_pipeline(config: Optional[TopicModelConfig] = None) -> Pipeline:
    """
    Restituisce una Pipeline sklearn:
    [LessonFeatureExtractor] -> [LogisticRegression]
    """
    cfg = config or TopicModelConfig()

    feature_extractor = LessonFeatureExtractor(
        config=cfg.text_features,
        use_meta_features=cfg.use_meta_features,
    )

    clf = LogisticRegression(
        C=cfg.C,
        max_iter=cfg.max_iter,
        n_jobs=-1,
    )

    pipe = Pipeline(
        steps=[
            ("features", feature_extractor),
            ("clf", clf),
        ]
    )
    return pipe


def train_topic_model(
    df: pd.DataFrame,
    config: Optional[TopicModelConfig] = None,
) -> Pipeline:
    """
    Allena la pipeline sul DataFrame `df`.

    Richiede:
      - df["text"]
      - df["topic"] come label di addestramento
    """
    if "topic" not in df.columns:
        raise KeyError("Expected 'topic' column in training DataFrame.")

    pipe = build_topic_pipeline(config)
    X = df
    y = df["topic"].astype(str)
    pipe.fit(X, y)
    return pipe


def save_topic_model(pipeline: Pipeline, path: str) -> None:
    """Salva la pipeline (feature + modello) su disco."""
    joblib.dump(pipeline, path)


def load_topic_model(path: str) -> Pipeline:
    """Carica una pipeline precedentemente salvata."""
    return joblib.load(path)
