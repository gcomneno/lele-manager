from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .features import LessonFeatureExtractor, TextFeatureConfig
from lele_manager.core.paths import topic_model_path


@dataclass
class TopicModelConfig:
    """Config della pipeline di classificazione topic."""
    text_features: TextFeatureConfig = field(default_factory=TextFeatureConfig)
    C: float = 4.0
    max_iter: int = 1_000
    use_meta_features: bool = True


def build_topic_pipeline(config: Optional[TopicModelConfig] = None) -> Pipeline:
    cfg = config or TopicModelConfig()

    feature_extractor = LessonFeatureExtractor(
        config=cfg.text_features,
        use_meta_features=cfg.use_meta_features,
    )

    clf = LogisticRegression(
        C=cfg.C,
        max_iter=cfg.max_iter,
    )

    return Pipeline(steps=[("features", feature_extractor), ("clf", clf)])


def train_topic_model(
    df: pd.DataFrame,
    config: Optional[TopicModelConfig] = None,
) -> Pipeline:
    if "topic" not in df.columns:
        raise KeyError("Expected 'topic' column in training DataFrame.")

    y = df["topic"].astype(str)
    unique_topics = sorted(y.dropna().unique())
    n_classes = len(unique_topics)

    if n_classes < 2:
        raise ValueError(
            "Topic model: servono almeno 2 topic diversi per il training.\n"
            f"Trovata 1 sola classe di topic: {unique_topics!r}.\n\n"
            "Assegna topic più granulari (es. 'python', 'cpp', 'linux', 'writing', ...)\n"
            "oppure rivedi l'import da vault prima di rilanciare il training."
        )

    pipe = build_topic_pipeline(config)
    pipe.fit(df, y)
    return pipe


def save_topic_model(pipeline: Pipeline, path: str | Path | None = None) -> Path:
    """
    Salva la pipeline (feature + modello) su disco.

    Se path è None, salva nel path XDG di default.
    Ritorna il Path effettivo usato.
    """
    p = Path(path).expanduser().resolve() if path is not None else topic_model_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, p)
    return p


def load_topic_model(path: str | Path | None = None) -> Pipeline:
    """
    Carica una pipeline precedentemente salvata.

    Se path è None, carica dal path XDG di default.
    """
    p = Path(path).expanduser().resolve() if path is not None else topic_model_path()
    return joblib.load(p)
