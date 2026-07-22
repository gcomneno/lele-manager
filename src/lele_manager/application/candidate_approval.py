"""Approve exactly one reviewed candidate into the canonical Markdown vault.

Only the six documented metadata keys are accepted. Unknown keys are rejected;
generated ``id`` and ``provenance`` therefore cannot be supplied or replaced.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
import hashlib
import math
import re
import unicodedata
from typing import Protocol

from lele_manager.application.lesson_candidate import (
    CandidateNotFoundError,
    CandidateRepository,
    CandidateRepositoryError,
    CandidateReviewAction,
    CandidateReviewEvent,
    CandidateRevisionConflictError,
    CandidateState,
    DuplicateCandidateIdError,
    ImmutableCandidateFieldError,
    LessonCandidate,
)


class VaultWriteOutcome(str, Enum):
    CREATED = "created"
    IDENTICAL = "identical"


@dataclass(frozen=True)
class RefreshOutcome:
    refreshed: bool = True


@dataclass(frozen=True)
class CanonicalLessonSpec:
    lesson_id: str
    relative_path: str
    body: str
    topic: str
    source: str
    importance: int
    tags: tuple[str, ...]
    date: str
    title: str
    provenance: Mapping[str, object]


@dataclass(frozen=True)
class ApprovalResult:
    candidate_id: str
    candidate_revision: int
    lesson_id: str
    relative_vault_path: str
    vault_write_outcome: VaultWriteOutcome
    candidate_state_changed: bool
    refresh_outcome: RefreshOutcome


class CandidateApprovalError(Exception):
    """Base class for stable, controlled approval failures."""


class InvalidApprovalInputError(CandidateApprovalError):
    pass


class InvalidApprovalMetadataError(CandidateApprovalError):
    pass


class CandidateApprovalNotFoundError(CandidateApprovalError):
    pass


class InvalidApprovalLifecycleError(CandidateApprovalError):
    pass


class StaleApprovalRevisionError(CandidateApprovalError):
    pass


class ApprovalCollisionError(CandidateApprovalError):
    pass


class ApprovalPathCollisionError(ApprovalCollisionError):
    pass


class ApprovalIdentityCollisionError(ApprovalCollisionError):
    pass


class ApprovalVaultStorageError(CandidateApprovalError):
    pass


class ApprovalCandidatePersistenceError(CandidateApprovalError):
    pass


class ApprovalRefreshError(CandidateApprovalError):
    pass


class CanonicalVaultError(Exception):
    pass


class CanonicalVaultStorageError(CanonicalVaultError):
    pass


class CanonicalPathCollisionError(CanonicalVaultError):
    pass


class CanonicalIdentityCollisionError(CanonicalVaultError):
    pass


class DerivedRefreshPortError(Exception):
    pass


class CanonicalMarkdownVault(Protocol):
    def publish(self, lesson: CanonicalLessonSpec) -> VaultWriteOutcome: ...
    def verify(self, lesson: CanonicalLessonSpec) -> VaultWriteOutcome: ...


class DerivedArtifactRefresh(Protocol):
    def refresh(self) -> RefreshOutcome: ...


class PartialApprovalError(ApprovalCandidatePersistenceError):
    def __init__(
        self,
        candidate_id: str,
        lesson_id: str,
        relative_vault_path: str,
        vault_write_outcome: VaultWriteOutcome,
    ) -> None:
        self.candidate_id = candidate_id
        self.lesson_id = lesson_id
        self.relative_vault_path = relative_vault_path
        self.vault_write_outcome = vault_write_outcome
        super().__init__(
            "canonical lesson exists but candidate approval was not persisted"
        )


class PartialRefreshError(ApprovalRefreshError):
    def __init__(self, partial_result: ApprovalResult) -> None:
        self.partial_result = partial_result
        super().__init__(
            "canonical lesson and candidate approval succeeded but refresh failed"
        )


_CANDIDATE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_METADATA_KEYS = {"topic", "source", "importance", "tags", "date", "title"}


def _canonical_provenance_value(
    value: object, active: set[int] | None = None
) -> object:
    """Copy JSON-compatible provenance with recursively sorted object keys."""
    active = set() if active is None else active
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if math.isfinite(value):
            return value
        raise InvalidApprovalMetadataError("provenance must be JSON-compatible")
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise InvalidApprovalMetadataError(
                "provenance mapping keys must be strings"
            )
        identity = id(value)
        if identity in active:
            raise InvalidApprovalMetadataError("provenance must not be cyclic")
        active.add(identity)
        try:
            return {
                key: _canonical_provenance_value(value[key], active)
                for key in sorted(value)
            }
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise InvalidApprovalMetadataError("provenance must not be cyclic")
        active.add(identity)
        try:
            return [_canonical_provenance_value(item, active) for item in value]
        finally:
            active.remove(identity)
    raise InvalidApprovalMetadataError("provenance must be JSON-compatible")


def _string(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise InvalidApprovalMetadataError(f"{field} must be a non-empty string")
    if any("\ud800" <= char <= "\udfff" for char in value):
        raise InvalidApprovalMetadataError(f"{field} contains invalid Unicode")
    return value


def _slug(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")[:60] or "lesson"


def canonical_lesson_for(candidate: LessonCandidate) -> CanonicalLessonSpec:
    metadata = candidate.proposed_metadata
    if metadata is None or set(metadata) != _METADATA_KEYS:
        raise InvalidApprovalMetadataError(
            "proposed metadata must contain exactly topic, source, importance, tags, date and title"
        )
    topic = _string(metadata["topic"], "topic")
    if (
        topic in (".", "..")
        or topic != topic.strip()
        or "/" in topic
        or "\\" in topic
        or any(ord(character) < 32 or ord(character) == 127 for character in topic)
    ):
        raise InvalidApprovalMetadataError("topic must be one canonical path segment")
    source = _string(metadata["source"], "source")
    title = _string(metadata["title"], "title")
    importance = metadata["importance"]
    if type(importance) is not int or not 1 <= importance <= 5:
        raise InvalidApprovalMetadataError(
            "importance must be an integer from 1 through 5"
        )
    raw_tags = metadata["tags"]
    if (
        isinstance(raw_tags, (str, bytes))
        or not isinstance(raw_tags, Sequence)
        or not raw_tags
    ):
        raise InvalidApprovalMetadataError("tags must be a non-empty sequence")
    tags = tuple(_string(tag, "tag") for tag in raw_tags)
    raw_date = _string(metadata["date"], "date")
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError:
        raise InvalidApprovalMetadataError(
            "date must be a real ISO date in YYYY-MM-DD form"
        ) from None
    if parsed_date.isoformat() != raw_date or len(raw_date) != 10:
        raise InvalidApprovalMetadataError(
            "date must be a real ISO date in YYYY-MM-DD form"
        )
    body = candidate.effective_text
    if not body.strip():
        raise InvalidApprovalMetadataError("lesson body must be non-empty")
    suffix = hashlib.sha256(candidate.candidate_id.encode("ascii")).hexdigest()[:12]
    stem = f"{raw_date}.{_slug(title)}-{suffix}"
    lesson_id = f"{topic}/{stem}"
    provenance = candidate.provenance
    span = provenance.source_span
    trace: dict[str, object] = {
        "candidate_id": candidate.candidate_id,
        "chunk_index": provenance.chunk_index,
        "ingested_at": provenance.ingested_at.isoformat(),
        "run_metadata": _canonical_provenance_value(provenance.run_metadata),
        "source_fingerprint": provenance.source_fingerprint,
        "source_kind": provenance.source_kind.value,
        "source_logical_name": provenance.source_logical_name,
        "source_span": None if span is None else {"end": span.end, "start": span.start},
        "transformations": _canonical_provenance_value(provenance.transformations),
    }
    return CanonicalLessonSpec(
        lesson_id,
        f"{lesson_id}.md",
        body,
        topic,
        source,
        importance,
        tags,
        raw_date,
        title,
        trace,
    )


class CandidateApprovalService:
    def __init__(
        self,
        repository: CandidateRepository,
        vault: CanonicalMarkdownVault,
        refresh: DerivedArtifactRefresh,
        clock: Callable[[], datetime],
    ) -> None:
        self._repository = repository
        self._vault = vault
        self._refresh = refresh
        self._clock = clock

    @staticmethod
    def _candidate_error(error: CandidateRepositoryError) -> CandidateApprovalError:
        if isinstance(error, CandidateNotFoundError):
            return CandidateApprovalNotFoundError("candidate was not found")
        if isinstance(error, CandidateRevisionConflictError):
            return StaleApprovalRevisionError("candidate revision is stale")
        if isinstance(error, (DuplicateCandidateIdError, ImmutableCandidateFieldError)):
            return ApprovalCandidatePersistenceError("candidate persistence conflict")
        return ApprovalCandidatePersistenceError(
            "candidate persistence operation failed"
        )

    def _refresh_result(self, partial: ApprovalResult) -> ApprovalResult:
        try:
            outcome = self._refresh.refresh()
        except DerivedRefreshPortError:
            raise PartialRefreshError(partial) from None
        return replace(partial, refresh_outcome=outcome)

    def approve(self, candidate_id: str, *, expected_revision: int) -> ApprovalResult:
        if (
            type(candidate_id) is not str
            or _CANDIDATE_ID.fullmatch(candidate_id) is None
        ):
            raise InvalidApprovalInputError(
                "candidate ID must be a canonical SHA-256 identity"
            )
        try:
            current = self._repository.get(candidate_id)
        except CandidateRepositoryError as error:
            raise self._candidate_error(error) from None
        if type(expected_revision) is not int or expected_revision < 0:
            raise InvalidApprovalInputError(
                "expected revision must be a non-negative integer"
            )
        if current.revision != expected_revision:
            raise StaleApprovalRevisionError("candidate revision is stale")
        if current.state not in (CandidateState.IN_REVIEW, CandidateState.APPROVED):
            raise InvalidApprovalLifecycleError("candidate is not approvable")
        lesson = canonical_lesson_for(current)
        try:
            write_outcome = (
                self._vault.publish(lesson)
                if current.state is CandidateState.IN_REVIEW
                else self._vault.verify(lesson)
            )
        except CanonicalPathCollisionError:
            raise ApprovalPathCollisionError(
                "canonical lesson path collision"
            ) from None
        except CanonicalIdentityCollisionError:
            raise ApprovalIdentityCollisionError(
                "canonical lesson identity collision"
            ) from None
        except CanonicalVaultStorageError:
            raise ApprovalVaultStorageError(
                "canonical vault operation failed"
            ) from None

        changed = current.state is CandidateState.IN_REVIEW
        persisted = current
        if changed:
            occurred_at = self._clock()
            event = CandidateReviewEvent(
                revision=current.revision + 1,
                action=CandidateReviewAction.APPROVED,
                occurred_at=occurred_at,
                previous_state=CandidateState.IN_REVIEW,
                resulting_state=CandidateState.APPROVED,
            )
            approved = replace(
                current,
                state=CandidateState.APPROVED,
                revision=current.revision + 1,
                review_history=(*current.review_history, event),
            )
            try:
                persisted = self._repository.update(
                    candidate_id, approved, expected_revision=current.revision
                )
                confirmed = self._repository.get(candidate_id)
            except CandidateRepositoryError:
                raise PartialApprovalError(
                    candidate_id, lesson.lesson_id, lesson.relative_path, write_outcome
                ) from None
            if (
                persisted != approved
                or confirmed.candidate_id != candidate_id
                or confirmed.revision != current.revision + 1
                or confirmed != approved
                or confirmed.review_history[-1] != event
            ):
                raise PartialApprovalError(
                    candidate_id, lesson.lesson_id, lesson.relative_path, write_outcome
                )
            persisted = confirmed
        partial = ApprovalResult(
            candidate_id,
            persisted.revision,
            lesson.lesson_id,
            lesson.relative_path,
            write_outcome,
            changed,
            RefreshOutcome(refreshed=False),
        )
        return self._refresh_result(partial)
