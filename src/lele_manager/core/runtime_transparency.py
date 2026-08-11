from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

from platformdirs import PlatformDirs

from lele_manager.core.paths import (
    APP_NAME,
    DEFAULT_CANDIDATES_FILENAME,
    DEFAULT_DUPLICATE_DECISIONS_FILENAME,
    DEFAULT_DB_FILENAME,
    DEFAULT_TOPIC_MODEL_FILENAME,
    ENV_CACHE_DIR,
    ENV_DATA_DIR,
    ENV_DATA_PATH_DEPRECATED,
    ENV_MODEL_PATH_DEPRECATED,
)
from lele_manager.core.vault import DEFAULT_VAULT_DIRNAME, ENV_VAULT_DIR


RuntimePathRole = Literal[
    "authoritative_user_data",
    "persistent_application_state",
    "derived_rebuildable_artifact",
    "cache_temporary_state",
]

RuntimePathProvenanceKind = Literal[
    "configuration_override",
    "legacy_override",
    "platform_default",
    "product_default",
]


@dataclass(frozen=True)
class RuntimePathProvenance:
    kind: RuntimePathProvenanceKind
    variable: str | None = None
    deprecated: bool = False


@dataclass(frozen=True)
class RuntimePathDescription:
    key: str
    path: Path
    role: RuntimePathRole
    provenance: RuntimePathProvenance


def _environment(environment: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environment is None else environment


def _resolved(raw: str | Path) -> Path:
    return Path(raw).expanduser().resolve()


def _data_dir(
    environment: Mapping[str, str],
) -> tuple[Path, RuntimePathProvenance]:
    configured = environment.get(ENV_DATA_DIR)
    if configured:
        return (
            _resolved(configured),
            RuntimePathProvenance(
                kind="configuration_override",
                variable=ENV_DATA_DIR,
            ),
        )

    dirs = PlatformDirs(APP_NAME)
    return (
        _resolved(dirs.user_data_dir),
        RuntimePathProvenance(kind="platform_default"),
    )


def _cache_dir(
    environment: Mapping[str, str],
) -> tuple[Path, RuntimePathProvenance]:
    configured = environment.get(ENV_CACHE_DIR)
    if configured:
        return (
            _resolved(configured),
            RuntimePathProvenance(
                kind="configuration_override",
                variable=ENV_CACHE_DIR,
            ),
        )

    dirs = PlatformDirs(APP_NAME)
    return (
        _resolved(dirs.user_cache_dir),
        RuntimePathProvenance(kind="platform_default"),
    )


def describe_runtime_paths(
    environment: Mapping[str, str] | None = None,
) -> tuple[RuntimePathDescription, ...]:
    """Describe established runtime paths without creating or modifying them."""
    env = _environment(environment)

    configured_vault = env.get(ENV_VAULT_DIR)
    if configured_vault:
        vault_path = _resolved(configured_vault)
        vault_provenance = RuntimePathProvenance(
            kind="configuration_override",
            variable=ENV_VAULT_DIR,
        )
    else:
        vault_path = _resolved(Path.home() / DEFAULT_VAULT_DIRNAME)
        vault_provenance = RuntimePathProvenance(kind="product_default")

    data_dir, data_dir_provenance = _data_dir(env)
    cache_dir, cache_dir_provenance = _cache_dir(env)

    legacy_data_path = env.get(ENV_DATA_PATH_DEPRECATED)
    if legacy_data_path:
        projection_path = _resolved(legacy_data_path)
        projection_provenance = RuntimePathProvenance(
            kind="legacy_override",
            variable=ENV_DATA_PATH_DEPRECATED,
            deprecated=True,
        )
    else:
        projection_path = data_dir / DEFAULT_DB_FILENAME
        projection_provenance = data_dir_provenance

    legacy_model_path = env.get(ENV_MODEL_PATH_DEPRECATED)
    if legacy_model_path:
        topic_model_path = _resolved(legacy_model_path)
        topic_model_provenance = RuntimePathProvenance(
            kind="legacy_override",
            variable=ENV_MODEL_PATH_DEPRECATED,
            deprecated=True,
        )
    else:
        topic_model_path = cache_dir / DEFAULT_TOPIC_MODEL_FILENAME
        topic_model_provenance = cache_dir_provenance

    return (
        RuntimePathDescription(
            key="vault",
            path=vault_path,
            role="authoritative_user_data",
            provenance=vault_provenance,
        ),
        RuntimePathDescription(
            key="application_data",
            path=data_dir,
            role="persistent_application_state",
            provenance=data_dir_provenance,
        ),
        RuntimePathDescription(
            key="vault_registry",
            path=data_dir / "vault-registry.json",
            role="persistent_application_state",
            provenance=data_dir_provenance,
        ),
        RuntimePathDescription(
            key="lesson_projection",
            path=projection_path,
            role="derived_rebuildable_artifact",
            provenance=projection_provenance,
        ),
        RuntimePathDescription(
            key="candidate_staging",
            path=data_dir / DEFAULT_CANDIDATES_FILENAME,
            role="persistent_application_state",
            provenance=data_dir_provenance,
        ),
        RuntimePathDescription(
            key="duplicate_decisions",
            path=data_dir / DEFAULT_DUPLICATE_DECISIONS_FILENAME,
            role="persistent_application_state",
            provenance=data_dir_provenance,
        ),
        RuntimePathDescription(
            key="cache",
            path=cache_dir,
            role="cache_temporary_state",
            provenance=cache_dir_provenance,
        ),
        RuntimePathDescription(
            key="topic_model",
            path=topic_model_path,
            role="derived_rebuildable_artifact",
            provenance=topic_model_provenance,
        ),
    )
