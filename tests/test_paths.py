from __future__ import annotations

from pathlib import Path

from lele_manager.paths import lessons_path, topic_model_path
from lele_manager.core.vault_registry import VaultRegistryStore, active_vault_context


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

    context = active_vault_context()
    assert lp == tmp_path / ".local" / "share" / "lele-manager" / "vaults" / context.vault_id / "lessons.jsonl"
    assert mp == tmp_path / ".cache" / "lele-manager" / "vaults" / context.vault_id / "topic_model.joblib"


def test_env_override_dirs(monkeypatch, tmp_path: Path) -> None:
    data = tmp_path / "D"
    cache = tmp_path / "C"

    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache))
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("LELE_MODEL_PATH", raising=False)

    context = active_vault_context()
    assert lessons_path() == data / "vaults" / context.vault_id / "lessons.jsonl"
    assert topic_model_path() == cache / "vaults" / context.vault_id / "topic_model.joblib"
    second_dir = tmp_path / "second"
    second_dir.mkdir()
    second = VaultRegistryStore().register("Second", second_dir)
    second_context = VaultRegistryStore().context_for(second)
    assert second_context.projection_path != context.projection_path
    assert second_context.topic_model_path != context.topic_model_path


def test_no_repo_relative_db_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LELE_DATA_DIR", raising=False)
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    lp = lessons_path()
    # deve stare sotto ~/.local/share/... e NON contenere "data/lessons.jsonl" relativo
    assert "data/lessons.jsonl" not in str(lp).replace("\\", "/")
