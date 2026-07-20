"""Backend-neutral lesson-candidate domain and staging repository port.

Candidate identity is the SHA-256 digest of canonical JSON containing the
normalized candidate text and its source/chunk identity.  Ingestion timestamps,
run metadata, transformations, proposed metadata and lifecycle state are
deliberately excluded, so replaying identical input produces the same ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

from lele_manager.application.raw_source import (
    SourceKind,
    SourceSpan,
    normalize_line_endings,
)
from lele_manager.core.json_compat import canonical_json


class CandidateState(str, Enum):
    STAGED = "staged"
    IN_REVIEW = "in_review"
    REJECTED = "rejected"
    APPROVED = "approved"


class CandidateRepositoryError(Exception):
    """Base class for controlled candidate repository failures."""


class DuplicateCandidateIdError(CandidateRepositoryError):
    """A candidate ID already exists or occurs twice in storage."""


class CandidateNotFoundError(CandidateRepositoryError):
    """The requested candidate does not exist."""


class MalformedStagingDataError(CandidateRepositoryError):
    """Persisted staging data does not match the supported schema."""


class CandidateStorageError(CandidateRepositoryError):
    """The staging backend could not complete an I/O operation."""


class ImmutableCandidateFieldError(CandidateRepositoryError):
    """An update attempted to change candidate identity or provenance."""


def _validate_unicode(value: str, name: str) -> None:
    if any("\ud800" <= character <= "\udfff" for character in value):
        raise ValueError(f"{name} must not contain Unicode surrogate code points")


def _freeze_json(value: object, name: str, active: set[int]) -> object:
    """Copy a JSON value into recursively immutable domain containers."""
    if isinstance(value, str):
        _validate_unicode(value, name)
        return value
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must contain only JSON-compatible values")
        return value
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise ValueError(f"{name} must contain only JSON-compatible values (no cycles)")
        active.add(identity)
        try:
            frozen: dict[str, object] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{name} must contain only JSON-compatible values")
                _validate_unicode(key, f"{name} key")
                frozen[key] = _freeze_json(item, name, active)
            return MappingProxyType(frozen)
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError(f"{name} must contain only JSON-compatible values (no cycles)")
        active.add(identity)
        try:
            return tuple(_freeze_json(item, name, active) for item in value)
        finally:
            active.remove(identity)
    raise ValueError(f"{name} must contain only JSON-compatible values")


def _freeze_metadata(name: str, value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    frozen = _freeze_json(value, name, set())
    assert isinstance(frozen, Mapping)
    return frozen


@dataclass(frozen=True)
class CandidateProvenance:
    source_kind: SourceKind
    source_logical_name: str
    source_fingerprint: str
    ingested_at: datetime
    chunk_index: int | None = None
    source_span: SourceSpan | None = None
    run_metadata: Mapping[str, object] = field(default_factory=dict)
    transformations: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, SourceKind):
            raise TypeError("source kind must be a SourceKind")
        if not isinstance(self.source_logical_name, str) or not self.source_logical_name:
            raise ValueError("source logical name must not be empty")
        _validate_unicode(self.source_logical_name, "source logical name")
        if not isinstance(self.source_fingerprint, str) or not self.source_fingerprint:
            raise ValueError("source fingerprint must not be empty")
        _validate_unicode(self.source_fingerprint, "source fingerprint")
        if not isinstance(self.ingested_at, datetime):
            raise ValueError("ingestion timestamp must be timezone-aware")
        try:
            offset = self.ingested_at.utcoffset()
        except Exception:
            raise ValueError("ingestion timestamp must be timezone-aware") from None
        if offset is None:
            raise ValueError("ingestion timestamp must be timezone-aware")
        if self.chunk_index is not None and (
            isinstance(self.chunk_index, bool)
            or not isinstance(self.chunk_index, int)
            or self.chunk_index < 0
        ):
            raise ValueError("chunk index must be a non-negative integer or None")
        if self.source_span is not None and not isinstance(self.source_span, SourceSpan):
            raise TypeError("source span must be a SourceSpan or None")
        object.__setattr__(
            self, "run_metadata", _freeze_metadata("run metadata", self.run_metadata)
        )
        if not isinstance(self.transformations, tuple):
            raise TypeError("transformations must be a tuple")
        object.__setattr__(
            self,
            "transformations",
            tuple(
                _freeze_metadata("transformation metadata", transformation)
                for transformation in self.transformations
            ),
        )


@dataclass(frozen=True)
class LessonCandidate:
    text: str
    provenance: CandidateProvenance
    proposed_metadata: Mapping[str, object] | None = None
    state: CandidateState = CandidateState.STAGED
    candidate_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("candidate text must be a string")
        _validate_unicode(self.text, "candidate text")
        if not isinstance(self.provenance, CandidateProvenance):
            raise TypeError("candidate provenance must be CandidateProvenance")
        if self.proposed_metadata is not None:
            object.__setattr__(
                self,
                "proposed_metadata",
                _freeze_metadata("proposed metadata", self.proposed_metadata),
            )
        if not isinstance(self.state, CandidateState):
            raise TypeError("candidate state must be a CandidateState")

        normalized_text = normalize_line_endings(self.text)
        object.__setattr__(self, "text", normalized_text)
        span = self.provenance.source_span
        identity = {
            "chunk_index": self.provenance.chunk_index,
            "source_fingerprint": self.provenance.source_fingerprint,
            "source_kind": self.provenance.source_kind.value,
            "source_logical_name": self.provenance.source_logical_name,
            "source_span": None if span is None else {"end": span.end, "start": span.start},
            "text": normalized_text,
        }
        digest = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
        object.__setattr__(self, "candidate_id", f"sha256:{digest}")


class CandidateRepository(Protocol):
    """Create/read/list/update boundary for isolated staged candidates."""

    def create(self, candidate: LessonCandidate) -> LessonCandidate: ...

    def get(self, candidate_id: str) -> LessonCandidate: ...

    def list(self) -> Sequence[LessonCandidate]: ...

    def update(
        self, candidate_id: str, candidate: LessonCandidate
    ) -> LessonCandidate: ...
