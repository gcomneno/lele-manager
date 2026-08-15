"""Canonical lifecycle vocabulary and validation helpers for LeLe entries."""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal


LifecycleState = Literal["active", "review-needed", "deprecated", "archived"]
LIFECYCLE_STATES: tuple[LifecycleState, ...] = (
    "active",
    "review-needed",
    "deprecated",
    "archived",
)


class LifecycleValidationError(ValueError):
    pass


def normalize_lifecycle(value: object) -> LifecycleState:
    """Return the maintained lifecycle state; missing values are implicitly active."""
    if value is None:
        return "active"
    if not isinstance(value, str):
        raise LifecycleValidationError("lifecycle must be one of: active, review-needed, deprecated, archived")
    normalized = value.strip()
    if not normalized:
        return "active"
    if normalized not in LIFECYCLE_STATES:
        raise LifecycleValidationError("lifecycle must be one of: active, review-needed, deprecated, archived")
    return normalized


def normalize_superseded_by(value: object, *, lesson_id: str) -> str | None:
    """Normalize one optional stable-ID replacement reference."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise LifecycleValidationError("superseded_by must be a stable lesson ID")
    target = value.strip()
    if not target:
        return None
    if target == lesson_id:
        raise LifecycleValidationError("a lesson cannot supersede itself")
    return target

def validate_supersession_chain(
    *,
    lesson_id: str,
    superseded_by: str | None,
    resolve_superseded_by: Callable[[str], str | None],
) -> None:
    """Reject a supersession chain that reaches the lesson being authored."""
    current = superseded_by
    visited = {lesson_id}
    while current is not None:
        if current in visited:
            raise LifecycleValidationError(
                "superseded_by must not create a supersession cycle"
            )
        visited.add(current)
        current = resolve_superseded_by(current)
