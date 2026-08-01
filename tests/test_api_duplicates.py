from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from lele_manager.api import server


class Transformer:
    def transform(self, df: pd.DataFrame) -> np.ndarray:
        return np.asarray([[1.0, 0.0], [0.9, 0.1]])[: len(df)]


def test_duplicates_function_exact_only_without_model(monkeypatch) -> None:
    monkeypatch.setattr(server, "load_lessons_df", lambda: pd.DataFrame([{"id": "a", "text": "same"}, {"id": "b", "text": "same"}]))
    monkeypatch.setattr(server, "build_similarity_index", lambda _df: (_ for _ in ()).throw(AssertionError("model used")))
    report = server.duplicates(min_score=0.85, limit=None, exact_only=True)
    assert report.exact_pairs == 1


def test_duplicates_function_full_report_with_controlled_transformer(monkeypatch) -> None:
    df = pd.DataFrame([{"id": "a", "text": "alpha"}, {"id": "b", "text": "beta"}])

    class FailingTransformer:
        def transform(self, _df: pd.DataFrame) -> np.ndarray:
            raise AssertionError("precomputed matrix was not used")

    monkeypatch.setattr(server, "load_lessons_df", lambda: df)
    monkeypatch.setattr(
        server,
        "build_similarity_index",
        lambda _df: SimpleNamespace(
            transformer=FailingTransformer(),
            feature_matrix=np.asarray([[1.0, 0.0], [0.9, 0.1]]),
        ),
    )
    report = server.duplicates(min_score=0.8, limit=1, exact_only=False)
    assert report.near_pairs == 1
    assert report.pairs[0].kind == "near"


def test_duplicates_function_single_lesson_without_model(monkeypatch) -> None:
    monkeypatch.setattr(server, "load_lessons_df", lambda: pd.DataFrame([{"id": "a", "text": "only"}]))
    monkeypatch.setattr(server, "build_similarity_index", lambda _df: (_ for _ in ()).throw(AssertionError("model used")))
    report = server.duplicates(min_score=0.85, limit=None, exact_only=False)
    assert report.lessons_analyzed == 1
    assert report.pairs == []


def test_exact_only_works_without_model(monkeypatch) -> None:
    monkeypatch.setattr(server, "load_lessons_df", lambda: pd.DataFrame([{"id": "a", "text": "same"}, {"id": "b", "text": "same"}]))
    monkeypatch.setattr(server, "build_similarity_index", lambda _df: (_ for _ in ()).throw(AssertionError("model used")))
    response = TestClient(server.app).get("/duplicates", params={"exact_only": "true"})
    assert response.status_code == 200
    assert response.json()["exact_pairs"] == 1


def test_full_report_requires_model(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server, "load_lessons_df", lambda: pd.DataFrame([{"id": "a", "text": "a"}, {"id": "b", "text": "b"}]))
    monkeypatch.setattr(server, "MODEL_PATH", tmp_path / "missing.joblib")
    response = TestClient(server.app).get("/duplicates")
    assert response.status_code == 503
    assert "Modello" in response.json()["detail"]


def test_full_report_uses_fitted_transformer(monkeypatch) -> None:
    df = pd.DataFrame([{"id": "a", "text": "alpha"}, {"id": "b", "text": "beta"}])
    monkeypatch.setattr(server, "load_lessons_df", lambda: df)
    monkeypatch.setattr(
        server,
        "build_similarity_index",
        lambda _df: SimpleNamespace(
            transformer=Transformer(),
            feature_matrix=np.asarray([[1.0, 0.0], [0.9, 0.1]]),
        ),
    )
    response = TestClient(server.app).get("/duplicates", params={"min_score": 0.8, "limit": 1})
    assert response.status_code == 200
    assert response.json()["pairs"][0]["kind"] == "near"


def test_invalid_parameters_are_422() -> None:
    client = TestClient(server.app)
    assert client.get("/duplicates", params={"min_score": 1.2}).status_code == 422
    assert client.get("/duplicates", params={"limit": 0}).status_code == 422


def test_empty_dataset_is_valid_without_model(monkeypatch) -> None:
    monkeypatch.setattr(server, "load_lessons_df", lambda: pd.DataFrame())
    response = TestClient(server.app).get("/duplicates")
    assert response.status_code == 200
    assert response.json()["lessons_analyzed"] == 0
    assert response.json()["pairs"] == []


def test_duplicate_pairs_include_independent_read_only_lesson_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "load_lessons_df",
        lambda: pd.DataFrame(
            [
                {
                    "id": "repeated-id",
                    "text": "first independently inspectable lesson",
                    "title": "First",
                    "tags": ["one"],
                    "path": "first.md",
                },
                {
                    "id": "repeated-id",
                    "text": "second independently inspectable lesson",
                    "title": "Second",
                    "tags": ["two"],
                    "path": "second.md",
                },
            ]
        ),
    )
    response = TestClient(server.app).get("/duplicates", params={"exact_only": "true"})

    assert response.status_code == 200
    pair = response.json()["pairs"][0]
    assert pair["left_position"] == 0
    assert pair["right_position"] == 1
    assert pair["left_lesson"] == {
        "id": "repeated-id",
        "text": "first independently inspectable lesson",
        "topic": None,
        "source": None,
        "importance": None,
        "tags": ["one"],
        "date": None,
        "title": "First",
        "created_at": None,
        "path": "first.md",
    }
    assert pair["right_lesson"]["text"] == "second independently inspectable lesson"
    assert pair["right_lesson"]["title"] == "Second"
    assert pair["right_lesson"]["path"] == "second.md"
