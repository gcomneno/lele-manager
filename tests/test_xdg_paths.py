from pathlib import Path

from fastapi.testclient import TestClient

from lele_manager import config
from lele_manager.api import server


def test_default_paths_use_xdg_env(tmp_path: Path, monkeypatch) -> None:
    data_home = tmp_path / "xdg_data"
    cache_home = tmp_path / "xdg_cache"

    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))

    assert config.default_data_path() == data_home / "lele-manager" / "lessons.jsonl"
    assert config.default_model_path() == cache_home / "lele-manager" / "topic_model.joblib"


def test_health_uses_env_override_paths(tmp_path: Path, monkeypatch) -> None:
    data_path = tmp_path / "my_lessons.jsonl"
    model_path = tmp_path / "my_model.joblib"

    data_path.write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")

    monkeypatch.setenv("LELE_DATA_PATH", str(data_path))
    monkeypatch.setenv("LELE_MODEL_PATH", str(model_path))

    client = TestClient(server.app)
    resp = client.get("/health")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["has_data"] is True
    assert payload["has_model"] is True
