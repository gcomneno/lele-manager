"""Backend-neutral lesson-candidate domain and staging repository port.

Candidate identity is the SHA-256 digest of canonical JSON containing the
normalized immutable source text and its source/chunk identity.

Ingestion timestamps, run metadata, transformations, proposed text, proposed
metadata, lifecycle state, revision and review history are deliberately
excluded, so replaying identical source input produces the same candidate ID.
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


class CandidateReviewAction(str, Enum):
    REVISED = "revised"
    ACCEPTED = "accepted"
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


class CandidateRevisionConflictError(CandidateRepositoryError):
    """The persisted candidate revision differs from the expected revision."""


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
class CandidateReviewEvent:
    revision: int
    action: CandidateReviewAction
    occurred_at: datetime
    previous_state: CandidateState
    resulting_state: CandidateState
    reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("review event revision must be a positive integer")
        if type(self.action) is not CandidateReviewAction:
            raise TypeError("review event action must be a CandidateReviewAction")
        if type(self.occurred_at) is not datetime:
            raise TypeError("review event timestamp must be a datetime")
        try:
            offset = self.occurred_at.utcoffset()
        except Exception:
            raise ValueError("review event timestamp must be timezone-aware") from None
        if offset is None:
            raise ValueError("review event timestamp must be timezone-aware")
        if type(self.previous_state) is not CandidateState:
            raise TypeError("review event previous state must be a CandidateState")
        if type(self.resulting_state) is not CandidateState:
            raise TypeError("review event resulting state must be a CandidateState")
        if self.reason is not None:
            if type(self.reason) is not str or not self.reason.strip():
                raise ValueError("review event reason must be None or a non-empty string")
            _validate_unicode(self.reason, "review event reason")

        allowed = {
            CandidateReviewAction.REVISED: (
                CandidateState.STAGED,
                CandidateState.STAGED,
            ),
            CandidateReviewAction.ACCEPTED: (
                CandidateState.STAGED,
                CandidateState.IN_REVIEW,
            ),
        }
        if self.action in allowed and (
            self.previous_state,
            self.resulting_state,
        ) != allowed[self.action]:
            raise ValueError("review event action does not match its state transition")
        if self.action is CandidateReviewAction.REJECTED and (
            self.previous_state not in (CandidateState.STAGED, CandidateState.IN_REVIEW)
            or self.resulting_state is not CandidateState.REJECTED
        ):
            raise ValueError("review event action does not match its state transition")
        if self.action is CandidateReviewAction.APPROVED and (
            self.previous_state is not CandidateState.IN_REVIEW
            or self.resulting_state is not CandidateState.APPROVED
        ):
            raise ValueError("review event action does not match its state transition")


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
    proposed_text: str | None = None
    revision: int = 0
    review_history: tuple[CandidateReviewEvent, ...] = ()
    candidate_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("candidate text must be a string")
        _validate_unicode(self.text, "candidate text")
        if not isinstance(self.provenance, CandidateProvenance):
            raise TypeError("candidate provenance must be CandidateProvenance")
        if self.proposed_text is not None:
            if type(self.proposed_text) is not str or not self.proposed_text.strip():
                raise ValueError("proposed text must be None or a non-whitespace string")
            _validate_unicode(self.proposed_text, "proposed text")
            object.__setattr__(
                self, "proposed_text", normalize_line_endings(self.proposed_text)
            )
        if self.proposed_metadata is not None:
            object.__setattr__(
                self,
                "proposed_metadata",
                _freeze_metadata("proposed metadata", self.proposed_metadata),
            )
        if not isinstance(self.state, CandidateState):
            raise TypeError("candidate state must be a CandidateState")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("candidate revision must be a non-negative integer")
        if not isinstance(self.review_history, tuple):
            raise TypeError("candidate review history must be a tuple")
        for expected_revision, event in enumerate(self.review_history, start=1):
            if type(event) is not CandidateReviewEvent:
                raise TypeError("candidate review history must contain review events")
            if event.revision != expected_revision:
                raise ValueError("review event revisions must be exactly 1..revision")
            if expected_revision > 1:
                previous = self.review_history[expected_revision - 2]
                if previous.resulting_state is not event.previous_state:
                    raise ValueError("review events must form a consistent state chain")
        if self.review_history:
            if len(self.review_history) != self.revision:
                raise ValueError("review event revisions must be exactly 1..revision")
            if self.review_history[-1].resulting_state is not self.state:
                raise ValueError("review history final state must equal candidate state")
        elif self.revision != 0:
            raise ValueError("empty review history requires revision zero")

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

    @property
    def effective_text(self) -> str:
        return self.proposed_text if self.proposed_text is not None else self.text


class CandidateRepository(Protocol):
    """Create/read/list/update boundary for isolated staged candidates."""

    def create(self, candidate: LessonCandidate) -> LessonCandidate: ...

    def get(self, candidate_id: str) -> LessonCandidate: ...

    def list(self) -> Sequence[LessonCandidate]: ...

    def update(
        self,
        candidate_id: str,
        candidate: LessonCandidate,
        *,
        expected_revision: int,
    ) -> LessonCandidate: ...
