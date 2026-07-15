"""Application composition for projection persistence.

JSONL remains the default compatibility adapter.  Consumers should request the
neutral port here instead of constructing an adapter themselves.
"""

from pathlib import Path

from lele_manager.adapters.jsonl_projection_store import (
    JsonlLegacyAppendFacade,
    JsonlProjectionStore,
)
from lele_manager.core.projection_store import ProjectionStore


def projection_store(path: Path) -> ProjectionStore:
    """Return the configured projection store (JSONL during issue #92)."""
    return JsonlProjectionStore(path)


def legacy_jsonl_append_facade(path: Path) -> JsonlLegacyAppendFacade:
    """Return the explicitly JSONL-specific legacy append compatibility API."""
    return JsonlLegacyAppendFacade(path)
