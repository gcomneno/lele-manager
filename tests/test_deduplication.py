from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lele_manager.core.deduplication import find_duplicates


class ControlledTransformer:
    def __init__(self, matrix: list[list[float]]) -> None:
        self.matrix = np.asarray(matrix, dtype=float)
        self.calls = 0

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        self.calls += 1
        assert len(df) == len(self.matrix)
        return self.matrix


def test_empty_and_single_lesson_reports() -> None:
    empty = find_duplicates(pd.DataFrame(), exact_only=True)
    single = find_duplicates(pd.DataFrame([{"id": "a", "text": "one"}]), exact_only=False)
    assert empty.lessons_analyzed == empty.total_pairs == 0
    assert single.lessons_analyzed == 1
    assert single.pairs == ()


def test_duplicate_id_keeps_both_positions() -> None:
    df = pd.DataFrame([{"id": "same", "text": "alpha"}, {"id": "same", "text": "beta"}])
    report = find_duplicates(df, exact_only=True)
    assert report.pairs[0].reasons == ("duplicate_id",)
    assert (report.pairs[0].left_position, report.pairs[0].right_position) == (0, 1)


def test_exact_text_uses_prudent_normalization() -> None:
    df = pd.DataFrame(
        [
            {"id": "a", "text": "\nCaffé  \r\nbody\t \r\n"},
            {"id": "b", "text": "Caffé\nbody"},
        ]
    )
    pair = find_duplicates(df, exact_only=True).pairs[0]
    assert pair.kind == "exact"
    assert "exact_text" in pair.reasons


def test_exact_text_without_metadata_is_not_marked_equivalent_metadata() -> None:
    df = pd.DataFrame([{"id": "a", "text": "same"}, {"id": "b", "text": "same"}])
    pair = find_duplicates(df, exact_only=True).pairs[0]
    assert pair.reasons == ("exact_text",)


def test_exact_text_with_equal_significant_metadata_is_marked_equivalent() -> None:
    df = pd.DataFrame(
        [
            {"id": "a", "text": "same", "topic": " Python "},
            {"id": "b", "text": "same", "topic": "python"},
        ]
    )
    pair = find_duplicates(df, exact_only=True).pairs[0]
    assert "equivalent_metadata" in pair.reasons


def test_same_title_with_different_text_is_not_exact() -> None:
    df = pd.DataFrame(
        [{"id": "a", "title": " Same title ", "text": "alpha"}, {"id": "b", "title": "same  TITLE", "text": "beta"}]
    )
    assert find_duplicates(df, exact_only=True).pairs == ()


def test_near_threshold_transform_once_and_no_mirror_or_self() -> None:
    df = pd.DataFrame([{"id": "a", "text": "a"}, {"id": "b", "text": "b"}, {"id": "c", "text": "c"}])
    transformer = ControlledTransformer([[1, 0], [0.9, 0.1], [0, 1]])
    report = find_duplicates(df, transformer=transformer, min_score=0.8)
    assert transformer.calls == 1
    assert [(p.left_id, p.right_id) for p in report.pairs] == [("a", "b")]


def test_below_threshold_is_excluded() -> None:
    df = pd.DataFrame([{"id": "a", "text": "a"}, {"id": "b", "text": "b"}])
    report = find_duplicates(df, transformer=ControlledTransformer([[1, 0], [0.5, 0.5]]), min_score=0.8)
    assert report.pairs == ()


def test_zero_min_score_keeps_negative_cosine() -> None:
    df = pd.DataFrame([{"id": "a", "text": "a"}, {"id": "b", "text": "b"}])
    matrix = np.asarray([[1.0, 0.0], [-1.0, 0.0]])
    report = find_duplicates(
        df,
        transformer=ControlledTransformer(matrix.tolist()),
        min_score=0.0,
    )
    assert len(report.pairs) == 1
    assert report.pairs[0].score == pytest.approx(-1.0)
    assert find_duplicates(df, feature_matrix=matrix, min_score=0.1).pairs == ()


def test_precomputed_feature_matrix_is_used_and_validated() -> None:
    df = pd.DataFrame([{"id": "a", "text": "a"}, {"id": "b", "text": "b"}])
    transformer = ControlledTransformer([[0.0, 1.0], [0.0, 1.0]])
    report = find_duplicates(
        df,
        transformer=transformer,
        feature_matrix=np.asarray([[1.0, 0.0], [0.9, 0.1]]),
        min_score=0.8,
    )
    assert transformer.calls == 0
    assert report.near_pairs == 1

    with pytest.raises(ValueError, match="same number of rows"):
        find_duplicates(df, feature_matrix=np.asarray([[1.0, 0.0]]))


def test_exact_only_ignores_transformer_and_feature_matrix() -> None:
    class FailingTransformer:
        def transform(self, df: pd.DataFrame) -> np.ndarray:
            raise AssertionError("transformer used")

    df = pd.DataFrame([{"id": "a", "text": "same"}, {"id": "b", "text": "same"}])
    report = find_duplicates(
        df,
        transformer=FailingTransformer(),  # type: ignore[arg-type]
        feature_matrix=np.asarray([[1.0, 0.0]]),
        exact_only=True,
    )
    assert report.exact_pairs == 1


def test_exact_pair_is_not_repeated_as_near() -> None:
    df = pd.DataFrame([{"id": "a", "text": "same"}, {"id": "b", "text": "same"}])
    report = find_duplicates(df, transformer=ControlledTransformer([[1, 0], [1, 0]]), min_score=0.0)
    assert len(report.pairs) == 1
    assert report.pairs[0].kind == "exact"


def test_metadata_signals_and_shared_tags() -> None:
    base = {"topic": "Python", "source": "Book", "date": "2026-01-01", "title": "Fixtures"}
    df = pd.DataFrame(
        [
            {"id": "a", "text": "alpha", "tags": ["Testing", "pytest"], **base},
            {"id": "b", "text": "beta", "tags": ["testing", "mock"], **base},
        ]
    )
    pair = find_duplicates(df, transformer=ControlledTransformer([[1, 0], [1, 0]]), min_score=0.8).pairs[0]
    assert pair.reasons == ("same_title", "same_topic", "same_source", "same_date", "shared_tags")
    assert pair.shared_tags == ("Testing",)


def test_set_tag_display_is_deterministic() -> None:
    df = pd.DataFrame(
        [
            {"id": "a", "text": "alpha", "tags": {"python", "Python"}},
            {"id": "b", "text": "beta", "tags": {"PYTHON"}},
        ]
    )
    pair = find_duplicates(df, feature_matrix=np.asarray([[1, 0], [1, 0]]), min_score=0.8).pairs[0]
    assert pair.shared_tags == ("Python",)


def test_deterministic_order_and_limit_preserve_full_counts() -> None:
    df = pd.DataFrame(
        [{"id": "z", "text": "same"}, {"id": "a", "text": "same"}, {"id": "b", "text": "different"}]
    )
    report = find_duplicates(
        df,
        transformer=ControlledTransformer([[1, 0], [1, 0], [0.9, 0.1]]),
        min_score=0.8,
        limit=1,
    )
    assert report.total_pairs == 3
    assert len(report.pairs) == 1
    assert report.pairs[0].kind == "exact"


def test_three_duplicate_ids_do_not_lose_records() -> None:
    df = pd.DataFrame([{"id": "x", "text": str(i)} for i in range(3)])
    report = find_duplicates(df, exact_only=True)
    assert len(report.pairs) == 3
    assert {(p.left_position, p.right_position) for p in report.pairs} == {(0, 1), (0, 2), (1, 2)}


@pytest.mark.parametrize("score", [-0.1, 1.1, float("nan")])
def test_invalid_min_score(score: float) -> None:
    with pytest.raises(ValueError, match="min_score"):
        find_duplicates(pd.DataFrame(), exact_only=True, min_score=score)
