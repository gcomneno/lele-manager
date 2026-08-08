from __future__ import annotations

from pathlib import Path

from lele_manager.core import runtime_transparency
from lele_manager.core.runtime_transparency import describe_runtime_paths


class _FakePlatformDirs:
    def __init__(self, _app_name: str) -> None:
        self.user_data_dir = "/platform/data/lele-manager"
        self.user_cache_dir = "/platform/cache/lele-manager"


def _by_key():
    return {item.key: item for item in describe_runtime_paths()}


def test_platform_and_product_defaults_are_pure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(runtime_transparency, "PlatformDirs", _FakePlatformDirs)
    monkeypatch.setattr(
        runtime_transparency.Path,
        "home",
        classmethod(lambda cls: tmp_path / "home"),
    )

    for variable in (
        "LELE_VAULT_DIR",
        "LELE_DATA_DIR",
        "LELE_CACHE_DIR",
        "LELE_DATA_PATH",
        "LELE_MODEL_PATH",
    ):
        monkeypatch.delenv(variable, raising=False)

    paths = _by_key()

    assert paths["vault"].path == (tmp_path / "home" / "LeLeVault").resolve()
    assert paths["vault"].provenance.kind == "product_default"

    assert paths["application_data"].path == Path(
        "/platform/data/lele-manager"
    ).resolve()
    assert paths["application_data"].provenance.kind == "platform_default"

    assert paths["lesson_projection"].path == (
        Path("/platform/data/lele-manager") / "lessons.jsonl"
    ).resolve()
    assert paths["candidate_staging"].path == (
        Path("/platform/data/lele-manager") / "candidates.json"
    ).resolve()

    assert paths["cache"].path == Path("/platform/cache/lele-manager").resolve()
    assert paths["cache"].provenance.kind == "platform_default"

    assert paths["topic_model"].path == (
        Path("/platform/cache/lele-manager") / "topic_model.joblib"
    ).resolve()

    assert not (tmp_path / "home").exists()


def test_directory_overrides_report_reliable_provenance_without_writes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    data = tmp_path / "data"
    cache = tmp_path / "cache"

    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache))
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("LELE_MODEL_PATH", raising=False)

    paths = _by_key()

    assert paths["vault"].path == vault.resolve()
    assert paths["vault"].provenance.variable == "LELE_VAULT_DIR"

    assert paths["application_data"].path == data.resolve()
    assert paths["application_data"].provenance.variable == "LELE_DATA_DIR"

    assert paths["lesson_projection"].path == data.resolve() / "lessons.jsonl"
    assert paths["lesson_projection"].provenance.variable == "LELE_DATA_DIR"

    assert paths["candidate_staging"].path == data.resolve() / "candidates.json"
    assert paths["candidate_staging"].provenance.variable == "LELE_DATA_DIR"

    assert paths["cache"].path == cache.resolve()
    assert paths["cache"].provenance.variable == "LELE_CACHE_DIR"

    assert paths["topic_model"].path == cache.resolve() / "topic_model.joblib"
    assert paths["topic_model"].provenance.variable == "LELE_CACHE_DIR"

    assert not vault.exists()
    assert not data.exists()
    assert not cache.exists()


def test_deprecated_file_overrides_are_explicit_and_side_effect_free(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    projection = tmp_path / "legacy" / "lessons.jsonl"
    model = tmp_path / "legacy-model" / "topic_model.joblib"

    monkeypatch.setenv("LELE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("LELE_DATA_PATH", str(projection))
    monkeypatch.setenv("LELE_MODEL_PATH", str(model))

    paths = _by_key()

    projection_description = paths["lesson_projection"]
    assert projection_description.path == projection.resolve()
    assert projection_description.provenance.kind == "legacy_override"
    assert projection_description.provenance.variable == "LELE_DATA_PATH"
    assert projection_description.provenance.deprecated is True

    model_description = paths["topic_model"]
    assert model_description.path == model.resolve()
    assert model_description.provenance.kind == "legacy_override"
    assert model_description.provenance.variable == "LELE_MODEL_PATH"
    assert model_description.provenance.deprecated is True

    assert paths["candidate_staging"].path == data_dir.resolve() / "candidates.json"

    assert not data_dir.exists()
    assert not cache_dir.exists()
    assert not projection.parent.exists()
    assert not model.parent.exists()


def test_semantic_roles_match_storage_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LELE_VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("LELE_MODEL_PATH", raising=False)

    paths = _by_key()

    assert paths["vault"].role == "authoritative_user_data"
    assert paths["application_data"].role == "persistent_application_state"
    assert paths["candidate_staging"].role == "persistent_application_state"
    assert paths["lesson_projection"].role == "derived_rebuildable_artifact"
    assert paths["topic_model"].role == "derived_rebuildable_artifact"
    assert paths["cache"].role == "cache_temporary_state"
