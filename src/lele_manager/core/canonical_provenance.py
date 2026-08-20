"""Validation and normalization for canonical lesson provenance."""

from __future__ import annotations

from collections.abc import Mapping
import math


class CanonicalProvenanceValidationError(ValueError):
    """Canonical provenance is not safely representable."""


def normalize_canonical_provenance(
    value: object,
    active: set[int] | None = None,
) -> object:
    active = set() if active is None else active

    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise CanonicalProvenanceValidationError(
                "canonical provenance mapping keys must be strings"
            )
        identity = id(value)
        if identity in active:
            raise CanonicalProvenanceValidationError(
                "canonical provenance must not be cyclic"
            )
        active.add(identity)
        try:
            return {
                key: normalize_canonical_provenance(value[key], active)
                for key in sorted(value)
            }
        finally:
            active.remove(identity)

    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise CanonicalProvenanceValidationError(
                "canonical provenance must not be cyclic"
            )
        active.add(identity)
        try:
            return [
                normalize_canonical_provenance(item, active)
                for item in value
            ]
        finally:
            active.remove(identity)

    if value is None or type(value) in (bool, int, str):
        return value

    if type(value) is float and math.isfinite(value):
        return value

    raise CanonicalProvenanceValidationError(
        "canonical provenance must contain only JSON-compatible values"
    )
