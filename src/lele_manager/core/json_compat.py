"""Shared JSON compatibility helpers."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Return the canonical JSON representation used for persisted records."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def json_native(value: Any) -> Any:
    """Return the JSON-native structure produced by canonical persistence."""
    return json.loads(canonical_json(value))
