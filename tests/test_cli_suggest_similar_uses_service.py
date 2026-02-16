from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_suggest_similar_calls_service_by_text(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from lele_manager.cli import suggest_similar as mod

    data_path = tmp_path / "lessons.jsonl"
    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": "hello world", "topic": "t"},
            {"id": "2", "text": "hello there", "topic": "t"},
        ],
    )

    # Avoid real model I/O
    monkeypatch.setattr(mod, "load_topic_model", lambda *_a, **_kw: object())

    # Dummy index that provides a transformer
    class _DummyTransformer:
        def transform(self, df: pd.DataFrame):
            # Not used, but keeps compatibility if something calls it
            return [[0.0] for _ in range(len(df))]

    class _DummyIndex:
        transformer = _DummyTransformer()

    monkeypatch.setattr(
        mod.LessonSimilarityIndex,
        "from_topic_pipeline",
        staticmethod(lambda **_kw: _DummyIndex()),
    )

    calls: dict[str, object] = {}

    def _fake_similar_by_text(*, df, query_text, transformer, top_k, min_score, ranking=None):
        calls["kind"] = "text"
        calls["query_text"] = query_text
        calls["top_k"] = top_k
        calls["min_score"] = min_score
        calls["transformer_is_dummy"] = isinstance(transformer, _DummyTransformer)
        return []

    monkeypatch.setattr(mod, "similar_by_text", _fake_similar_by_text)

    mod.main(
        [
            "--input",
            str(data_path),
            "--model",
            str(tmp_path / "topic_model.joblib"),
            "--text",
            "hello",
            "--top-k",
            "7",
            "--min-score",
            "0.25",
        ]
    )

    out = capsys.readouterr().out
    assert "Query basata su testo esplicito" in out

    assert calls["kind"] == "text"
    assert calls["query_text"] == "hello"
    assert calls["top_k"] == 7
    assert calls["min_score"] == 0.25
    assert calls["transformer_is_dummy"] is True


def test_suggest_similar_calls_service_by_lesson_id(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from lele_manager.cli import suggest_similar as mod

    data_path = tmp_path / "lessons.jsonl"
    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": "hello world", "topic": "t"},
            {"id": "2", "text": "hello there", "topic": "t"},
        ],
    )

    monkeypatch.setattr(mod, "load_topic_model", lambda *_a, **_kw: object())

    class _DummyTransformer:
        def transform(self, df: pd.DataFrame):
            return [[0.0] for _ in range(len(df))]

    class _DummyIndex:
        transformer = _DummyTransformer()

    monkeypatch.setattr(
        mod.LessonSimilarityIndex,
        "from_topic_pipeline",
        staticmethod(lambda **_kw: _DummyIndex()),
    )

    calls: dict[str, object] = {}

    def _fake_similar_by_lesson_id(*, df, lesson_id, transformer, top_k, min_score, ranking=None):
        calls["kind"] = "id"
        calls["lesson_id"] = lesson_id
        calls["top_k"] = top_k
        calls["min_score"] = min_score
        calls["transformer_is_dummy"] = isinstance(transformer, _DummyTransformer)
        return []

    monkeypatch.setattr(mod, "similar_by_lesson_id", _fake_similar_by_lesson_id)

    mod.main(
        [
            "--input",
            str(data_path),
            "--model",
            str(tmp_path / "topic_model.joblib"),
            "--from-id",
            "1",
            "--top-k",
            "3",
            "--min-score",
            "0.0",
        ]
    )

    out = capsys.readouterr().out
    assert "Query basata su lesson esistente" in out

    assert calls["kind"] == "id"
    assert calls["lesson_id"] == "1"
    assert calls["top_k"] == 3
    assert calls["min_score"] == 0.0
    assert calls["transformer_is_dummy"] is True
