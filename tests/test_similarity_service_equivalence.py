import pytest
import pandas as pd

from lele_manager.ml.similarity import LessonSimilarityIndex
from lele_manager.ml.similarity_service import similar_by_text, similar_by_lesson_id
from lele_manager.ml.features import LessonFeatureExtractor
from lele_manager.core.ranking import SimilarityRankingConfig


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        [
            {"id": "1", "text": "python pandas commonterm", "importance": 1.0},
            {"id": "2", "text": "python sklearn commonterm", "importance": 1.0},
            {"id": "3", "text": "python linux commonterm", "importance": 1.0},
        ]
    )


@pytest.fixture
def fitted_transformer(sample_df):
    transformer = LessonFeatureExtractor()
    transformer.fit(sample_df)
    return transformer


def test_similarity_service_equivalence_free_text(sample_df, fitted_transformer):
    ranking = SimilarityRankingConfig()
    query_text = "python pandas"

    # Baseline
    index = LessonSimilarityIndex.from_dataframe(df=sample_df, transformer=fitted_transformer)
    expected = index.most_similar(
        query_text=query_text,
        top_k=ranking.top_k_default,
        min_score=ranking.min_score_default,
        ranking=ranking,
    )

    # Service
    actual = similar_by_text(
        sample_df,
        query_text,
        transformer=fitted_transformer,
        ranking=ranking,
    )

    # 👇 QUI (subito dopo actual/expected)
    assert len(actual) == len(expected)

    assert [r.lesson_id for r in actual] == [r.lesson_id for r in expected]
    for a, e in zip(actual, expected):
        assert a.score == pytest.approx(e.score)


def test_similarity_service_equivalence_lesson_id(sample_df, fitted_transformer):
    ranking = SimilarityRankingConfig()
    target_id = "1"

    # Baseline
    index = LessonSimilarityIndex.from_dataframe(df=sample_df, transformer=fitted_transformer)
    query_text = str(sample_df[sample_df["id"] == target_id].iloc[0]["text"])
    expected = index.most_similar(
        query_text=query_text,
        top_k=ranking.top_k_default,
        min_score=ranking.min_score_default,
        ranking=ranking,
    )

    # Service
    actual = similar_by_lesson_id(
        sample_df,
        target_id,
        transformer=fitted_transformer,
        ranking=ranking,
    )

    # 👇 QUI
    assert len(actual) == len(expected)

    assert [r.lesson_id for r in actual] == [r.lesson_id for r in expected]
    for a, e in zip(actual, expected):
        assert a.score == pytest.approx(e.score)


def test_similarity_service_equivalence_empty_query(sample_df, fitted_transformer):
    ranking = SimilarityRankingConfig()
    query_text = ""

    index = LessonSimilarityIndex.from_dataframe(df=sample_df, transformer=fitted_transformer)
    expected = index.most_similar(
        query_text=query_text,
        top_k=ranking.top_k_default,
        min_score=ranking.min_score_default,
        ranking=ranking,
    )

    actual = similar_by_text(
        sample_df,
        query_text,
        transformer=fitted_transformer,
        ranking=ranking,
    )

    assert len(actual) == len(expected)
    assert [r.lesson_id for r in actual] == [r.lesson_id for r in expected]
    for a, e in zip(actual, expected):
        assert a.score == pytest.approx(e.score)

def test_similarity_service_equivalence_min_score_nonzero(sample_df, fitted_transformer):
    ranking = SimilarityRankingConfig()
    query_text = "python pandas"
    min_score = 0.01  # evita borderline

    index = LessonSimilarityIndex.from_dataframe(df=sample_df, transformer=fitted_transformer)
    expected = index.most_similar(
        query_text=query_text,
        top_k=ranking.top_k_default,
        min_score=min_score,
        ranking=ranking,
    )

    actual = similar_by_text(
        sample_df,
        query_text,
        transformer=fitted_transformer,
        ranking=ranking,
        min_score=min_score,
    )

    assert len(actual) == len(expected)
    assert [r.lesson_id for r in actual] == [r.lesson_id for r in expected]
    for a, e in zip(actual, expected):
        assert a.score == pytest.approx(e.score)

def test_similarity_service_equivalence_top_k_override(sample_df, fitted_transformer):
    ranking = SimilarityRankingConfig()
    query_text = "python pandas"
    top_k = 2

    index = LessonSimilarityIndex.from_dataframe(df=sample_df, transformer=fitted_transformer)
    expected = index.most_similar(
        query_text=query_text,
        top_k=top_k,
        min_score=ranking.min_score_default,
        ranking=ranking,
    )

    actual = similar_by_text(
        sample_df,
        query_text,
        transformer=fitted_transformer,
        ranking=ranking,
        top_k=top_k,
    )

    assert len(actual) == len(expected)
    assert len(actual) == top_k  # qui sì, è voluto
    assert [r.lesson_id for r in actual] == [r.lesson_id for r in expected]
    for a, e in zip(actual, expected):
        assert a.score == pytest.approx(e.score)
