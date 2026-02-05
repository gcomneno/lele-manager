from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "lele-manager"


def xdg_data_home() -> Path:
    """XDG data home:
    - usa $XDG_DATA_HOME se presente
    - altrimenti fallback ~/.local/share
    """
    env = os.environ.get("XDG_DATA_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "share"


def xdg_cache_home() -> Path:
    """XDG cache home:
    - usa $XDG_CACHE_HOME se presente
    - altrimenti fallback ~/.cache
    """
    env = os.environ.get("XDG_CACHE_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache"


def default_data_path() -> Path:
    """Default dataset path (JSONL) usando XDG."""
    return xdg_data_home() / APP_DIR_NAME / "lessons.jsonl"


def default_model_path() -> Path:
    """Default model path usando XDG."""
    return xdg_cache_home() / APP_DIR_NAME / "topic_model.joblib"


def resolve_data_path() -> Path:
    """Dataset path con override via env var:
    - $LELE_DATA_PATH se presente
    - altrimenti default XDG
    """
    env = os.environ.get("LELE_DATA_PATH")
    return Path(env).expanduser() if env else default_data_path()


def resolve_model_path() -> Path:
    """Model path con override via env var:
    - $LELE_MODEL_PATH se presente
    - altrimenti default XDG
    """
    env = os.environ.get("LELE_MODEL_PATH")
    return Path(env).expanduser() if env else default_model_path()
