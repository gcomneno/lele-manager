import pytest
import pandas as pd
from lele_manager.ml.similarity_backend import TfidfLsaSimilarityBackend
from lele_manager.ml.features import LessonFeatureExtractor

@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {"id": "1", "text": "python pandas commonterm", "importance": 1.0},
        {"id": "2", "text": "python sklearn commonterm", "importance": 1.0},
        {"id": "3", "text": "linux bash commonterm", "importance": 1.0},
    ])

@pytest.fixture
def transformer(sample_df):
    tr = LessonFeatureExtractor()
    tr.fit(sample_df)
    return tr

def test_cache_key_consistency(sample_df, transformer):
    b = TfidfLsaSimilarityBackend(n_components=2)
    r1 = b.most_similar(df=sample_df, query_text="python pandas", transformer=transformer, top_k=2, min_score=0.0)
    r2 = b.most_similar(df=sample_df, query_text="python pandas", transformer=transformer, top_k=2, min_score=0.0)
    assert [x.lesson_id for x in r1] == [x.lesson_id for x in r2]
    assert [x.score for x in r1] == pytest.approx([x.score for x in r2])

def test_n_components_guardrail(sample_df, transformer):
    b = TfidfLsaSimilarityBackend(n_components=1000)  # oversized intentionally
    r = b.most_similar(df=sample_df, query_text="python pandas", transformer=transformer, top_k=2, min_score=0.0)
    assert len(r) <= 2
