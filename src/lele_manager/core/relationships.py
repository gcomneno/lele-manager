"""Canonical typed-relationship vocabulary and validation helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal, TypeAlias


RelationshipType = Literal[
    "derives-from",
    "corrects",
    "extends",
    "contradicts",
    "supersedes",
    "see-also",
]

CanonicalRelationshipType = Literal[
    "derives-from",
    "corrects",
    "extends",
    "contradicts",
    "see-also",
]

RELATIONSHIP_TYPES: tuple[RelationshipType, ...] = (
    "derives-from",
    "corrects",
    "extends",
    "contradicts",
    "supersedes",
    "see-also",
)

CANONICAL_RELATIONSHIP_TYPES: tuple[CanonicalRelationshipType, ...] = (
    "derives-from",
    "corrects",
    "extends",
    "contradicts",
    "see-also",
)

CanonicalRelationships: TypeAlias = dict[
    CanonicalRelationshipType,
    tuple[str, ...],
]


class RelationshipValidationError(ValueError):
    """Canonical relationship metadata violates the maintained contract."""


def normalize_relationships(
    value: object,
    *,
    lesson_id: str,
) -> CanonicalRelationships:
    """Normalize canonical generic relationships deterministically.

    ``supersedes`` deliberately has no representation in this mapping:
    supersession remains canonically represented by ``superseded_by`` on the
    lesson being replaced.

    Empty relation lists are omitted from the normalized representation.
    Target ordering is lexical and carries no semantic meaning.
    """
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise RelationshipValidationError(
            "relationships must be a mapping of relationship types to target-ID lists"
        )

    source_id = lesson_id.strip()
    normalized: CanonicalRelationships = {}

    for raw_type, raw_targets in value.items():
        if not isinstance(raw_type, str):
            raise RelationshipValidationError(
                "relationship type must be a string"
            )

        relation_type = raw_type.strip()

        if relation_type == "supersedes":
            raise RelationshipValidationError(
                "supersedes must use the canonical superseded_by contract"
            )

        if relation_type not in CANONICAL_RELATIONSHIP_TYPES:
            allowed = ", ".join(CANONICAL_RELATIONSHIP_TYPES)
            raise RelationshipValidationError(
                f"unknown relationship type {relation_type!r}; expected one of: {allowed}"
            )

        if not isinstance(raw_targets, (list, tuple)):
            raise RelationshipValidationError(
                f"relationships.{relation_type} must be a list of stable lesson IDs"
            )

        targets: list[str] = []
        seen: set[str] = set()

        for raw_target in raw_targets:
            if not isinstance(raw_target, str):
                raise RelationshipValidationError(
                    f"relationships.{relation_type} targets must be stable lesson IDs"
                )

            target = raw_target.strip()
            if not target:
                raise RelationshipValidationError(
                    f"relationships.{relation_type} must not contain blank targets"
                )

            if target == source_id:
                raise RelationshipValidationError(
                    f"relationships.{relation_type} must not reference the lesson itself"
                )

            if target in seen:
                raise RelationshipValidationError(
                    f"relationships.{relation_type} contains duplicate target {target!r}"
                )

            seen.add(target)
            targets.append(target)

        if targets:
            normalized[relation_type] = tuple(sorted(targets))

    return {
        relation_type: normalized[relation_type]
        for relation_type in CANONICAL_RELATIONSHIP_TYPES
        if relation_type in normalized
    }


def validate_relationship_targets(
    relationships: Mapping[
        CanonicalRelationshipType,
        Sequence[str],
    ],
    *,
    resolve_target_count: Callable[[str], int],
) -> None:
    """Require every explicitly authored target to resolve exactly once.

    This is an authoring-boundary guard. A later destructive operation may
    leave an already-canonical relationship broken; that condition is handled
    diagnostically rather than by silently rewriting the source lesson.
    """
    for relation_type in CANONICAL_RELATIONSHIP_TYPES:
        for target in relationships.get(relation_type, ()):
            matches = resolve_target_count(target)

            if matches == 1:
                continue

            if matches == 0:
                raise RelationshipValidationError(
                    f"relationships.{relation_type} target {target!r} "
                    "does not exist in the active Vault"
                )

            raise RelationshipValidationError(
                f"relationships.{relation_type} target {target!r} "
                "is ambiguous in the active Vault"
            )
