from __future__ import annotations

from pathlib import Path

from .paths import (
    DEFAULT_DB_FILENAME,
    DEFAULT_TOPIC_MODEL_FILENAME,
    data_dir,
    cache_dir,
    lessons_path,
    topic_model_path,
)


def default_data_path() -> Path:
    """
    Default dataset path (JSONL) usando XDG/platformdirs (app-specific).
    Nota: NON considera LELE_DATA_PATH (deprecated).
    """
    return data_dir() / DEFAULT_DB_FILENAME


def default_model_path() -> Path:
    """
    Default model path usando XDG/platformdirs (app-specific).
    Nota: NON considera LELE_MODEL_PATH (deprecated).
    """
    return cache_dir() / DEFAULT_TOPIC_MODEL_FILENAME


def resolve_data_path() -> Path:
    """
    Dataset path con override via env:
    - supporta LELE_DATA_PATH (deprecated, con warning in paths.py)
    - supporta LELE_DATA_DIR (nuovo)
    - altrimenti default XDG
    """
    return lessons_path()


def resolve_model_path() -> Path:
    """
    Model path con override via env:
    - supporta LELE_MODEL_PATH (deprecated, con warning in paths.py)
    - supporta LELE_CACHE_DIR (nuovo)
    - altrimenti default XDG
    """
    return topic_model_path()
