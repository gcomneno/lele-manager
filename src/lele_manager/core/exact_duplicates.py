from __future__ import annotations

from typing import Any
import unicodedata


def _value(value: Any) -> str:
    return "" if value is None else str(value)


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFC", _value(value)).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def is_exact_duplicate_record(left: Any, right: Any) -> bool:
    """Return whether two lesson-like records match duplicate-review exactness."""
    left_id = _value(left.get("id"))
    right_id = _value(right.get("id"))
    if left_id and left_id == right_id:
        return True
    left_text = _normalize_text(left.get("text"))
    return bool(left_text) and left_text == _normalize_text(right.get("text"))
