"""Backend-neutral human review workflow for staged lesson candidates.

Lifecycle policy:

- ``STAGED`` candidates may be revised, accepted or rejected.
- Revision keeps the candidate ``STAGED``.
- Acceptance moves a candidate from ``STAGED`` to ``IN_REVIEW``.
- Rejection moves ``STAGED`` or ``IN_REVIEW`` to ``REJECTED``.
- ``REJECTED`` and ``APPROVED`` are terminal for this service.
- Every successful operation appends exactly one review event and increments
  the optimistic-concurrency revision exactly once.
- Repeated or otherwise invalid transitions fail deterministically without
  calling the clock or writing candidate storage.

Approval into the canonical vault remains outside this module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime

from lele_manager.application.lesson_candidate import (
    CandidateNotFoundError,
    CandidateRepository,
    CandidateRepositoryError,
    CandidateReviewAction,
    CandidateReviewEvent,
    CandidateRevisionConflictError,
    CandidateState,
    DuplicateCandidateIdError,
    LessonCandidate,
)
from lele_manager.application.raw_source import SourceKind


class CandidateReviewError(Exception):
    """Base class for controlled candidate-review failures."""


class ReviewCandidateNotFoundError(CandidateReviewError):
    """The requested candidate does not exist."""


class InvalidCandidateTransitionError(CandidateReviewError):
    """The requested operation is not valid in the current lifecycle state."""


class StaleCandidateRevisionError(CandidateReviewError):
    """The caller's expected revision is no longer current."""


class CandidateReviewConflictError(CandidateReviewError):
    """Candidate storage contains a conflicting identity."""


class CandidateReviewStorageError(CandidateReviewError):
    """The candidate repository could not complete the operation."""


class InvalidCandidateReviewInputError(CandidateReviewError):
    """Review input does not satisfy the public application contract."""


def _non_empty_string(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise InvalidCandidateReviewInputError(f"{name} must be a non-empty string")
    if any("\ud800" <= character <= "\udfff" for character in value):
        raise InvalidCandidateReviewInputError(f"{name} contains invalid Unicode")
    return value


def _optional_reason(value: object) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, "reason")


def _expected_revision(value: object) -> int:
    if type(value) is not int or value < 0:
        raise InvalidCandidateReviewInputError(
            "expected revision must be a non-negative integer"
        )
    return value


@dataclass(frozen=True)
class CandidateReviewFilter:
    state: CandidateState | None = None
    source_fingerprint: str | None = None
    source_kind: SourceKind | None = None
    source_logical_name: str | None = None
    chunk_index: int | None = None

    def __post_init__(self) -> None:
        if self.state is not None and type(self.state) is not CandidateState:
            raise InvalidCandidateReviewInputError("state must be a CandidateState or None")
        if self.source_kind is not None and type(self.source_kind) is not SourceKind:
            raise InvalidCandidateReviewInputError(
                "source kind must be a SourceKind or None"
            )
        for value, name in (
            (self.source_fingerprint, "source fingerprint"),
            (self.source_logical_name, "source logical name"),
        ):
            if value is not None:
                _non_empty_string(value, name)
        if self.chunk_index is not None and (
            type(self.chunk_index) is not int or self.chunk_index < 0
        ):
            raise InvalidCandidateReviewInputError(
                "chunk index must be a non-negative integer or None"
            )


class CandidateReviewService:
    def __init__(
        self, repository: CandidateRepository, clock: Callable[[], datetime]
    ) -> None:
        self._repository = repository
        self._clock = clock

    @staticmethod
    def _translate_repository_error(error: CandidateRepositoryError) -> CandidateReviewError:
        if isinstance(error, CandidateNotFoundError):
            return ReviewCandidateNotFoundError("candidate was not found")
        if isinstance(error, CandidateRevisionConflictError):
            return StaleCandidateRevisionError("candidate revision is stale")
        if isinstance(error, DuplicateCandidateIdError):
            return CandidateReviewConflictError("candidate identity conflict")
        return CandidateReviewStorageError("candidate storage operation failed")

    def _get(self, candidate_id: str) -> LessonCandidate:
        _non_empty_string(candidate_id, "candidate ID")
        try:
            return self._repository.get(candidate_id)
        except CandidateRepositoryError as error:
            raise self._translate_repository_error(error) from None

    def get_candidate(self, candidate_id: str) -> LessonCandidate:
        return self._get(candidate_id)

    def list_candidates(
        self, filters: CandidateReviewFilter | None = None
    ) -> tuple[LessonCandidate, ...]:
        if filters is None:
            filters = CandidateReviewFilter()
        elif type(filters) is not CandidateReviewFilter:
            raise InvalidCandidateReviewInputError(
                "filters must be a CandidateReviewFilter or None"
            )
        try:
            candidates = self._repository.list()
        except CandidateRepositoryError as error:
            raise self._translate_repository_error(error) from None
        seen: set[str] = set()
        result: list[LessonCandidate] = []
        for candidate in candidates:
            if candidate.candidate_id in seen:
                raise CandidateReviewConflictError("duplicate candidate identity")
            seen.add(candidate.candidate_id)
            provenance = candidate.provenance
            if filters.state is not None and candidate.state is not filters.state:
                continue
            if (
                filters.source_fingerprint is not None
                and provenance.source_fingerprint != filters.source_fingerprint
            ):
                continue
            if filters.source_kind is not None and provenance.source_kind is not filters.source_kind:
                continue
            if (
                filters.source_logical_name is not None
                and provenance.source_logical_name != filters.source_logical_name
            ):
                continue
            if filters.chunk_index is not None and provenance.chunk_index != filters.chunk_index:
                continue
            result.append(candidate)
        return tuple(sorted(result, key=lambda candidate: candidate.candidate_id))

    def _write(
        self,
        candidate_id: str,
        *,
        expected_revision: int,
        action: CandidateReviewAction,
        resulting_state: CandidateState,
        reason: str | None,
        proposed_text: str | None = None,
        proposed_metadata: Mapping[str, object] | None = None,
    ) -> LessonCandidate:
        current = self._get(candidate_id)
        expected = _expected_revision(expected_revision)
        if current.revision != expected:
            raise StaleCandidateRevisionError("candidate revision is stale")

        allowed = {
            CandidateReviewAction.REVISED: (CandidateState.STAGED,),
            CandidateReviewAction.ACCEPTED: (CandidateState.STAGED,),
            CandidateReviewAction.REJECTED: (
                CandidateState.STAGED,
                CandidateState.IN_REVIEW,
            ),
        }
        if current.state not in allowed[action]:
            raise InvalidCandidateTransitionError("candidate transition is not allowed")

        validated_reason = _optional_reason(reason)
        try:
            validated = (
                replace(
                    current,
                    proposed_text=proposed_text,
                    proposed_metadata=proposed_metadata,
                )
                if action is CandidateReviewAction.REVISED
                else current
            )
        except (TypeError, ValueError):
            raise InvalidCandidateReviewInputError(
                "invalid candidate review input"
            ) from None

        occurred_at = self._clock()
        event = CandidateReviewEvent(
            revision=expected + 1,
            action=action,
            occurred_at=occurred_at,
            previous_state=current.state,
            resulting_state=resulting_state,
            reason=validated_reason,
        )
        updated = replace(
            validated,
            state=resulting_state,
            revision=expected + 1,
            review_history=current.review_history + (event,),
        )
        try:
            return self._repository.update(
                candidate_id, updated, expected_revision=expected
            )
        except CandidateRepositoryError as error:
            raise self._translate_repository_error(error) from None

    def revise_candidate(
        self,
        candidate_id: str,
        *,
        expected_revision: int,
        proposed_text: str | None,
        proposed_metadata: Mapping[str, object] | None,
        reason: str | None = None,
    ) -> LessonCandidate:
        return self._write(
            candidate_id,
            expected_revision=expected_revision,
            action=CandidateReviewAction.REVISED,
            resulting_state=CandidateState.STAGED,
            reason=reason,
            proposed_text=proposed_text,
            proposed_metadata=proposed_metadata,
        )

    def accept_candidate(
        self, candidate_id: str, *, expected_revision: int, reason: str | None = None
    ) -> LessonCandidate:
        return self._write(
            candidate_id,
            expected_revision=expected_revision,
            action=CandidateReviewAction.ACCEPTED,
            resulting_state=CandidateState.IN_REVIEW,
            reason=reason,
        )

    def reject_candidate(
        self, candidate_id: str, *, expected_revision: int, reason: str | None = None
    ) -> LessonCandidate:
        return self._write(
            candidate_id,
            expected_revision=expected_revision,
            action=CandidateReviewAction.REJECTED,
            resulting_state=CandidateState.REJECTED,
            reason=reason,
        )
