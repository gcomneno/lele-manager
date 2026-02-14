from __future__ import annotations

from pathlib import Path

from lele_manager.paths import lessons_path, topic_model_path


def test_xdg_defaults_use_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LELE_DATA_DIR", raising=False)
    monkeypatch.delenv("LELE_CACHE_DIR", raising=False)
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("LELE_MODEL_PATH", raising=False)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    lp = lessons_path()
    mp = topic_model_path()

    assert lp == tmp_path / ".local" / "share" / "lele-manager" / "lessons.jsonl"
    assert mp == tmp_path / ".cache" / "lele-manager" / "topic_model.joblib"


def test_env_override_dirs(monkeypatch, tmp_path: Path) -> None:
    data = tmp_path / "D"
    cache = tmp_path / "C"

    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache))
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("LELE_MODEL_PATH", raising=False)

    assert lessons_path() == data / "lessons.jsonl"
    assert topic_model_path() == cache / "topic_model.joblib"


def test_no_repo_relative_db_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LELE_DATA_DIR", raising=False)
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    lp = lessons_path()
    # deve stare sotto ~/.local/share/... e NON contenere "data/lessons.jsonl" relativo
    assert "data/lessons.jsonl" not in str(lp).replace("\\", "/")
