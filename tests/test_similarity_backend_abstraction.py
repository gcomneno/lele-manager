import pandas as pd

from lele_manager.core.ranking import SimilarityRankingConfig
from lele_manager.ml.features import LessonFeatureExtractor
from lele_manager.ml.similarity_backend import TfidfSimilarityBackend
from lele_manager.ml.similarity_service import similar_by_lesson_id, similar_by_text


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id": "1", "text": "python pandas commonterm", "importance": 1.0},
            {"id": "2", "text": "python sklearn commonterm", "importance": 1.0},
            {"id": "3", "text": "python linux commonterm", "importance": 1.0},
        ]
    )


def _fitted_transformer(df: pd.DataFrame) -> LessonFeatureExtractor:
    tr = LessonFeatureExtractor()
    tr.fit(df)
    return tr


def test_backend_abstraction_similar_by_text_equivalent():
    df = _sample_df()
    transformer = _fitted_transformer(df)
    cfg = SimilarityRankingConfig()
    backend = TfidfSimilarityBackend()

    r1 = similar_by_text(df, "hello", transformer, top_k=cfg.top_k_default, min_score=cfg.min_score_default)
    r2 = similar_by_text(
        df,
        "hello",
        transformer,
        top_k=cfg.top_k_default,
        min_score=cfg.min_score_default,
        backend=backend,
    )
    assert r1 == r2


def test_backend_abstraction_similar_by_lesson_id_equivalent():
    df = _sample_df()
    transformer = _fitted_transformer(df)
    cfg = SimilarityRankingConfig()
    backend = TfidfSimilarityBackend()
    lesson_id = "1"

    r1 = similar_by_lesson_id(df, lesson_id, transformer, top_k=cfg.top_k_default, min_score=cfg.min_score_default)
    r2 = similar_by_lesson_id(
        df,
        lesson_id,
        transformer,
        top_k=cfg.top_k_default,
        min_score=cfg.min_score_default,
        backend=backend,
    )
    assert r1 == r2
