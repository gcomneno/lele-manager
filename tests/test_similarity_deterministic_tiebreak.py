import numpy as np
import pandas as pd

from lele_manager.ml.features import LessonFeatureExtractor
from lele_manager.ml.similarity import LessonSimilarityIndex


def test_most_similar_tiebreaker_lesson_id_asc(monkeypatch) -> None:
    # 3 lessons with intentionally unsorted ids
    df = pd.DataFrame(
        [
            {"id": "b", "text": "same", "importance": 0},
            {"id": "a", "text": "same", "importance": 0},
            {"id": "c", "text": "same", "importance": 0},
        ]
    )

    transformer = LessonFeatureExtractor()
    transformer.fit(df)
    index = LessonSimilarityIndex.from_dataframe(df=df, transformer=transformer, id_column="id")

    # Force equal scores to exercise tie-breaker deterministically
    def fake_cosine_similarity(query_vec, feature_matrix):
        return np.array([[1.0, 1.0, 1.0]], dtype=float)

    # Patch the cosine_similarity used inside the module
    import lele_manager.ml.similarity as sim_mod
    monkeypatch.setattr(sim_mod, "cosine_similarity", fake_cosine_similarity)

    res = index.most_similar("whatever", top_k=3, min_score=0.0)
    assert [r.lesson_id for r in res] == ["a", "b", "c"]
