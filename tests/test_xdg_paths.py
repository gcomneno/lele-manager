from pathlib import Path

from fastapi.testclient import TestClient

from lele_manager import config
from lele_manager.api import server
from lele_manager.core.vault_registry import active_vault_context


def test_default_paths_use_xdg_env(tmp_path: Path, monkeypatch) -> None:
    data_home = tmp_path / "xdg_data"
    cache_home = tmp_path / "xdg_cache"

    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))

    assert config.default_data_path() == data_home / "lele-manager" / "lessons.jsonl"
    assert config.default_model_path() == cache_home / "lele-manager" / "topic_model.joblib"


def test_health_ignores_deprecated_file_overrides_in_registry_mode(tmp_path: Path, monkeypatch) -> None:
    server.DATA_PATH = None
    server.MODEL_PATH = None

    data_path = tmp_path / "my_lessons.jsonl"
    model_path = tmp_path / "my_model.joblib"

    data_path.write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")

    monkeypatch.setenv("LELE_DATA_PATH", str(data_path))
    monkeypatch.setenv("LELE_MODEL_PATH", str(model_path))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(tmp_path / "vault"))
    context = active_vault_context()

    client = TestClient(server.app)
    resp = client.get("/health")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["has_data"] is False
    assert payload["has_model"] is False
    assert server.get_data_path() == context.projection_path
    assert server.get_model_path() == context.topic_model_path
