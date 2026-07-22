from __future__ import annotations

import logging
import os
from pathlib import Path
from platformdirs import PlatformDirs

log = logging.getLogger(__name__)

APP_NAME = "lele-manager"

# New env (dir-level)
ENV_DATA_DIR = "LELE_DATA_DIR"
ENV_CACHE_DIR = "LELE_CACHE_DIR"

# Deprecated env (file-level) — support for 1 release
ENV_DATA_PATH_DEPRECATED = "LELE_DATA_PATH"
ENV_MODEL_PATH_DEPRECATED = "LELE_MODEL_PATH"

DEFAULT_DB_FILENAME = "lessons.jsonl"
DEFAULT_CANDIDATES_FILENAME = "candidates.json"
DEFAULT_TOPIC_MODEL_FILENAME = "topic_model.joblib"


def _warn_deprecated_env(var_name: str, replacement: str) -> None:
    log.warning(
        "Env var %s is DEPRECATED and will be removed in the next release. "
        "Use %s instead.",
        var_name,
        replacement,
    )


def data_dir() -> Path:
    """
    Base directory for persistent data.

    Priority:
    1) LELE_DATA_DIR (new)
    2) platformdirs user_data_dir (XDG on Linux)
    """
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    d = PlatformDirs(APP_NAME)
    p = Path(d.user_data_dir).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    """
    Base directory for cache/models.

    Priority:
    1) LELE_CACHE_DIR (new)
    2) platformdirs user_cache_dir (XDG on Linux)
    """
    env = os.environ.get(ENV_CACHE_DIR)
    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    d = PlatformDirs(APP_NAME)
    p = Path(d.user_cache_dir).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def lessons_path() -> Path:
    """
    Full path to lessons JSONL.

    Priority:
    1) LELE_DATA_PATH (deprecated, file-level)  -> warning
    2) data_dir()/lessons.jsonl
    """
    env_depr = os.environ.get(ENV_DATA_PATH_DEPRECATED)
    if env_depr:
        _warn_deprecated_env(ENV_DATA_PATH_DEPRECATED, ENV_DATA_DIR)
        p = Path(env_depr).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    p = data_dir() / DEFAULT_DB_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def candidates_path() -> Path:
    """Full path to the local TritaLeLe candidate staging document."""
    return data_dir() / DEFAULT_CANDIDATES_FILENAME


def topic_model_path() -> Path:
    """
    Full path to topic model.

    Priority:
    1) LELE_MODEL_PATH (deprecated, file-level) -> warning
    2) cache_dir()/topic_model.joblib
    """
    env_depr = os.environ.get(ENV_MODEL_PATH_DEPRECATED)
    if env_depr:
        _warn_deprecated_env(ENV_MODEL_PATH_DEPRECATED, ENV_CACHE_DIR)
        p = Path(env_depr).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    p = cache_dir() / DEFAULT_TOPIC_MODEL_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
