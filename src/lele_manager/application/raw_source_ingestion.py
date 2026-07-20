"""Backend-neutral orchestration for staging raw-source chunks.

Each repository ``create`` is its own staging operation; no rollback is
attempted.  A later failure can therefore leave earlier candidates staged.
Rerunning the same ingestion safely skips those successful candidates and
continues with the missing ones.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from lele_manager.application.lesson_candidate import (
    CandidateProvenance,
    CandidateRepository,
    CandidateRepositoryError,
    DuplicateCandidateIdError,
    LessonCandidate,
)
from lele_manager.application.raw_source import RawSource
from lele_manager.application.raw_source_chunking import (
    ChunkingSettings,
    RawSourceChunk,
    RawSourceChunker,
)


class RawSourceIngestionError(Exception):
    """Base class for controlled raw-source ingestion failures."""


class IngestionPlanError(RawSourceIngestionError):
    """The chunker returned an invalid plan for the requested raw source."""


class IngestionConflictError(RawSourceIngestionError):
    """A candidate ID is already associated with incompatible content."""

    def __init__(
        self, candidate_id: str | None, *, created_candidate_ids: Sequence[str] = ()
    ) -> None:
        super().__init__("candidate identity conflict during ingestion")
        self.candidate_id = candidate_id
        self.created_candidate_ids = tuple(created_candidate_ids)


class IngestionStagingError(RawSourceIngestionError):
    """The repository failed before any candidate was staged."""

    def __init__(
        self,
        message: str,
        *,
        failed_candidate_id: str | None = None,
        remaining_candidate_ids: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.failed_candidate_id = failed_candidate_id
        self.remaining_candidate_ids = tuple(remaining_candidate_ids)


class PartialIngestionError(RawSourceIngestionError):
    """A staging failure after one or more successful creates."""

    def __init__(
        self,
        *,
        created_candidate_ids: Sequence[str],
        failed_candidate_id: str,
        remaining_candidate_ids: Sequence[str],
    ) -> None:
        super().__init__("candidate staging failed after partial ingestion")
        self.created_candidate_ids = tuple(created_candidate_ids)
        self.failed_candidate_id = failed_candidate_id
        self.remaining_candidate_ids = tuple(remaining_candidate_ids)


@dataclass(frozen=True)
class RawSourceIngestionResult:
    """Immutable outcome of planning and optionally staging one raw source."""

    source_fingerprint: str
    planned_candidates: Sequence[LessonCandidate]
    created_candidate_ids: Sequence[str]
    skipped_candidate_ids: Sequence[str]
    pending_candidate_ids: Sequence[str]
    preview: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source_fingerprint, str) or not self.source_fingerprint:
            raise ValueError("source fingerprint must not be empty")
        if not isinstance(self.preview, bool):
            raise TypeError("preview must be a bool")

        for field_name in (
            "planned_candidates",
            "created_candidate_ids",
            "skipped_candidate_ids",
            "pending_candidate_ids",
        ):
            value = getattr(self, field_name)
            try:
                frozen = tuple(value)
            except TypeError:
                raise TypeError(f"{field_name} must be a sequence") from None
            object.__setattr__(self, field_name, frozen)

        if not all(
            isinstance(candidate, LessonCandidate)
            for candidate in self.planned_candidates
        ):
            raise TypeError("planned candidates must be LessonCandidate instances")
        groups = (
            self.created_candidate_ids,
            self.skipped_candidate_ids,
            self.pending_candidate_ids,
        )
        if not all(
            isinstance(candidate_id, str) and candidate_id
            for group in groups
            for candidate_id in group
        ):
            raise ValueError("candidate status IDs must be non-empty strings")

        candidate_ids = self.candidate_ids
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("planned candidate IDs must be unique")
        if any(
            candidate.provenance.source_fingerprint != self.source_fingerprint
            for candidate in self.planned_candidates
        ):
            raise ValueError("planned candidate fingerprints must match the result")
        if tuple(
            candidate.provenance.chunk_index
            for candidate in self.planned_candidates
        ) != tuple(range(len(self.planned_candidates))):
            raise ValueError("planned candidates must be in contiguous chunk-index order")
        flattened = tuple(item for group in groups for item in group)
        if len(flattened) != len(set(flattened)):
            raise ValueError("candidate status groups must be disjoint")
        if not set(flattened).issubset(candidate_ids):
            raise ValueError("candidate status IDs must belong to the plan")
        if set(flattened) != set(candidate_ids):
            raise ValueError("every planned candidate must have a status")
        plan_positions = {candidate_id: index for index, candidate_id in enumerate(candidate_ids)}
        if any(
            tuple(plan_positions[candidate_id] for candidate_id in group)
            != tuple(sorted(plan_positions[candidate_id] for candidate_id in group))
            for group in groups
        ):
            raise ValueError("candidate status IDs must preserve plan order")
        if self.preview and self.created_candidate_ids:
            raise ValueError("preview results cannot contain created candidates")
        if not self.preview and self.pending_candidate_ids:
            raise ValueError("non-preview results cannot contain pending candidates")

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(candidate.candidate_id for candidate in self.planned_candidates)

    @property
    def created_count(self) -> int:
        return len(self.created_candidate_ids)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_candidate_ids)

    @property
    def pending_count(self) -> int:
        return len(self.pending_candidate_ids)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_identity(candidate: LessonCandidate) -> tuple[object, ...]:
    provenance = candidate.provenance
    return (
        candidate.candidate_id,
        candidate.text,
        provenance.source_kind,
        provenance.source_logical_name,
        provenance.source_fingerprint,
        provenance.chunk_index,
        provenance.source_span,
    )


class RawSourceIngestionService:
    """Plan deterministic candidates and stage only candidates not yet present."""

    def __init__(
        self,
        chunker: RawSourceChunker,
        repository: CandidateRepository,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._chunker = chunker
        self._repository = repository
        self._clock = clock

    def ingest(
        self,
        source: RawSource,
        settings: ChunkingSettings,
        preview: bool = False,
    ) -> RawSourceIngestionResult:
        ingested_at = self._clock()
        chunks = tuple(self._chunker.chunk(source, settings))
        if not all(isinstance(chunk, RawSourceChunk) for chunk in chunks):
            raise IngestionPlanError("chunker returned an invalid ingestion plan")
        chunks = tuple(sorted(chunks, key=lambda chunk: chunk.index))
        for expected_index, chunk in enumerate(chunks):
            span = chunk.source_span
            if (
                chunk.index != expected_index
                or chunk.source_fingerprint != source.fingerprint
                or chunk.source_kind != source.kind
                or chunk.source_logical_name != source.logical_name
                or span.end > len(source.content)
                or chunk.text != source.content[span.start : span.end]
            ):
                raise IngestionPlanError("chunker returned an invalid ingestion plan")
        planned = tuple(
            self._candidate(chunk, settings, ingested_at) for chunk in chunks
        )
        if not planned:
            return RawSourceIngestionResult(
                source.fingerprint, (), (), (), (), preview
            )

        try:
            existing_candidates = self._repository.list()
        except DuplicateCandidateIdError:
            raise IngestionConflictError(None) from None
        except CandidateRepositoryError:
            raise IngestionStagingError("unable to inspect candidate staging") from None

        existing_by_id: dict[str, LessonCandidate] = {}
        for stored_candidate in existing_candidates:
            if stored_candidate.candidate_id in existing_by_id:
                raise IngestionConflictError(stored_candidate.candidate_id)
            existing_by_id[stored_candidate.candidate_id] = stored_candidate

        skipped: list[str] = []
        missing: list[LessonCandidate] = []
        for candidate in planned:
            existing = existing_by_id.get(candidate.candidate_id)
            if existing is None:
                missing.append(candidate)
            elif _stable_identity(existing) == _stable_identity(candidate):
                skipped.append(candidate.candidate_id)
            else:
                raise IngestionConflictError(candidate.candidate_id)

        if preview:
            return RawSourceIngestionResult(
                source.fingerprint,
                planned,
                (),
                tuple(skipped),
                tuple(candidate.candidate_id for candidate in missing),
                True,
            )

        created: list[str] = []
        for position, candidate in enumerate(missing):
            try:
                self._repository.create(candidate)
            except DuplicateCandidateIdError:
                raise IngestionConflictError(
                    candidate.candidate_id, created_candidate_ids=created
                ) from None
            except CandidateRepositoryError:
                remaining = tuple(
                    item.candidate_id for item in missing[position + 1 :]
                )
                if created:
                    raise PartialIngestionError(
                        created_candidate_ids=created,
                        failed_candidate_id=candidate.candidate_id,
                        remaining_candidate_ids=remaining,
                    ) from None
                raise IngestionStagingError(
                    "unable to stage candidate",
                    failed_candidate_id=candidate.candidate_id,
                    remaining_candidate_ids=remaining,
                ) from None
            created.append(candidate.candidate_id)

        return RawSourceIngestionResult(
            source.fingerprint, planned, tuple(created), tuple(skipped), (), False
        )

    @staticmethod
    def _candidate(
        chunk: RawSourceChunk,
        settings: ChunkingSettings,
        ingested_at: datetime,
    ) -> LessonCandidate:
        return LessonCandidate(
            text=chunk.text,
            provenance=CandidateProvenance(
                source_kind=chunk.source_kind,
                source_logical_name=chunk.source_logical_name,
                source_fingerprint=chunk.source_fingerprint,
                ingested_at=ingested_at,
                chunk_index=chunk.index,
                source_span=chunk.source_span,
                run_metadata={
                    "chunking": {
                        "max_characters": settings.max_characters,
                        "heading_context": chunk.heading_context,
                    }
                },
            ),
        )
