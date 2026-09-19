"""Application-level semantic Lesson Learned extraction for TritaLeLe.

This module deliberately owns no provider integration.  A semantic extractor
is an advisory operation port that receives deterministic raw-source chunks and
returns proposed Lesson Learned data.  LeLe Manager validates the proposal,
reconstructs trusted provenance from source chunks, stages candidates, and
retains all publication authority in the existing human review/approval flow.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Protocol

from lele_manager.application.lesson_candidate import (
    CandidateProvenance,
    CandidateRepository,
    CandidateRepositoryError,
    CandidateSourceEvidence,
    DuplicateCandidateIdError,
    LessonCandidate,
)
from lele_manager.application.raw_source import RawSource
from lele_manager.application.raw_source_chunking import (
    ChunkingSettings,
    RawSourceChunk,
    RawSourceChunker,
)
from lele_manager.application.raw_source_ingestion import (
    IngestionConflictError,
    IngestionPlanError,
    IngestionStagingError,
    PartialIngestionError,
)
from lele_manager.core.json_compat import canonical_json


class SemanticExtractionError(Exception):
    """Controlled semantic extraction failure."""


def _non_empty_text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if any("\ud800" <= character <= "\udfff" for character in value):
        raise ValueError(f"{name} must not contain Unicode surrogate code points")
    return value


@dataclass(frozen=True, slots=True)
class SemanticExtractionInput:
    """Validated, source-bounded input for one semantic extraction call."""

    chunks: tuple[RawSourceChunk, ...]

    def __post_init__(self) -> None:
        if type(self.chunks) is not tuple:
            raise TypeError("semantic extraction chunks must be a tuple")
        if not self.chunks:
            return
        if not all(type(chunk) is RawSourceChunk for chunk in self.chunks):
            raise TypeError(
                "semantic extraction chunks must contain RawSourceChunk values"
            )

        indexes = tuple(chunk.index for chunk in self.chunks)
        if len(indexes) != len(set(indexes)):
            raise ValueError("semantic extraction chunk indexes must be unique")
        if indexes != tuple(sorted(indexes)):
            raise ValueError(
                "semantic extraction chunks must be in ascending index order"
            )

        first = self.chunks[0]
        for chunk in self.chunks[1:]:
            if (
                chunk.source_fingerprint != first.source_fingerprint
                or chunk.source_kind is not first.source_kind
                or chunk.source_logical_name != first.source_logical_name
            ):
                raise ValueError("semantic extraction chunks must belong to one source")


@dataclass(frozen=True, slots=True)
class SemanticLessonProposal:
    """Advisory semantic proposal before trusted provenance is reconstructed."""

    title: str
    body: str
    rationale: str
    supporting_chunk_indexes: tuple[int, ...]
    topic: str | None = None
    tags: tuple[str, ...] = ()
    source_label: str | None = None
    importance: int | None = None

    def __post_init__(self) -> None:
        _non_empty_text(self.title, "proposal title")
        _non_empty_text(self.body, "proposal body")
        _non_empty_text(self.rationale, "proposal rationale")

        if type(self.supporting_chunk_indexes) is not tuple:
            raise TypeError("supporting chunk indexes must be a tuple")
        if not self.supporting_chunk_indexes:
            raise ValueError("semantic proposal must cite supporting chunks")
        if any(
            type(index) is not int or index < 0
            for index in self.supporting_chunk_indexes
        ):
            raise ValueError("supporting chunk indexes must be non-negative integers")
        if len(self.supporting_chunk_indexes) != len(
            set(self.supporting_chunk_indexes)
        ):
            raise ValueError("supporting chunk indexes must be unique")
        if self.supporting_chunk_indexes != tuple(
            sorted(self.supporting_chunk_indexes)
        ):
            raise ValueError("supporting chunk indexes must be ordered")

        if self.topic is not None:
            _non_empty_text(self.topic, "proposal topic")

        if type(self.tags) is not tuple:
            raise TypeError("proposal tags must be a tuple")
        for tag in self.tags:
            _non_empty_text(tag, "proposal tag")

        if self.source_label is not None:
            _non_empty_text(self.source_label, "proposal source label")

        if self.importance is not None and (
            type(self.importance) is not int or not 1 <= self.importance <= 5
        ):
            raise ValueError(
                "proposal importance must be an integer from 1 through 5 or None"
            )


@dataclass(frozen=True, slots=True)
class SemanticLessonExtractionResult:
    """Zero, one, or many validated semantic lesson proposals."""

    proposals: tuple[SemanticLessonProposal, ...]

    def __post_init__(self) -> None:
        if type(self.proposals) is not tuple:
            raise TypeError("semantic extraction proposals must be a tuple")
        if not all(
            type(proposal) is SemanticLessonProposal for proposal in self.proposals
        ):
            raise TypeError(
                "semantic extraction proposals must contain SemanticLessonProposal values"
            )


class SemanticLessonExtractor(Protocol):
    """Consumer-owned semantic extraction operation port."""

    def execute(
        self,
        value: SemanticExtractionInput,
    ) -> SemanticLessonExtractionResult: ...


@dataclass(frozen=True, slots=True)
class SemanticIngestionResult:
    """Outcome of semantic proposal planning/staging for one source."""

    source_fingerprint: str
    planned_candidates: tuple[LessonCandidate, ...]
    created_candidate_ids: tuple[str, ...]
    skipped_candidate_ids: tuple[str, ...]
    pending_candidate_ids: tuple[str, ...]
    preview: bool

    def __post_init__(self) -> None:
        _non_empty_text(self.source_fingerprint, "source fingerprint")
        if type(self.planned_candidates) is not tuple or not all(
            type(candidate) is LessonCandidate for candidate in self.planned_candidates
        ):
            raise TypeError("planned candidates must be a tuple of LessonCandidate")
        if type(self.preview) is not bool:
            raise TypeError("preview must be a bool")

        groups = (
            self.created_candidate_ids,
            self.skipped_candidate_ids,
            self.pending_candidate_ids,
        )
        if any(type(group) is not tuple for group in groups):
            raise TypeError("candidate status IDs must be tuples")
        if any(
            type(candidate_id) is not str or not candidate_id
            for group in groups
            for candidate_id in group
        ):
            raise ValueError("candidate status IDs must be non-empty strings")

        candidate_ids = self.candidate_ids
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("planned semantic candidate IDs must be unique")

        flattened = tuple(item for group in groups for item in group)
        if len(flattened) != len(set(flattened)):
            raise ValueError("candidate status groups must be disjoint")
        if set(flattened) != set(candidate_ids):
            raise ValueError("every semantic candidate must have one status")
        if self.preview and self.created_candidate_ids:
            raise ValueError("preview cannot contain created candidates")
        if not self.preview and self.pending_candidate_ids:
            raise ValueError("non-preview cannot contain pending candidates")

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


def semantic_derivation_id(
    proposal: SemanticLessonProposal,
) -> str:
    """Return a stable LeLe-owned semantic derivation identity."""

    material = {
        "body": proposal.body,
        "supporting_chunk_indexes": proposal.supporting_chunk_indexes,
        "title": proposal.title,
    }
    digest = hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def lesson_candidate_from_semantic_proposal(
    proposal: SemanticLessonProposal,
    chunks: tuple[RawSourceChunk, ...],
    *,
    ingested_at: datetime,
    extraction_metadata: Mapping[str, object],
) -> LessonCandidate:
    """Map one advisory proposal to a staged candidate with trusted evidence."""

    if type(proposal) is not SemanticLessonProposal:
        raise TypeError("proposal must be a SemanticLessonProposal")
    if type(chunks) is not tuple or not all(
        type(chunk) is RawSourceChunk for chunk in chunks
    ):
        raise TypeError("chunks must be a tuple of RawSourceChunk")
    if type(ingested_at) is not datetime or ingested_at.utcoffset() is None:
        raise ValueError("ingested_at must be timezone-aware")
    if not isinstance(extraction_metadata, Mapping):
        raise TypeError("extraction metadata must be a mapping")

    by_index = {chunk.index: chunk for chunk in chunks}
    supporting: list[RawSourceChunk] = []
    for index in proposal.supporting_chunk_indexes:
        chunk = by_index.get(index)
        if chunk is None:
            raise SemanticExtractionError(
                "semantic proposal references an unknown source chunk"
            )
        supporting.append(chunk)

    first = supporting[0]
    evidence = tuple(
        CandidateSourceEvidence(
            chunk_index=chunk.index,
            source_span=chunk.source_span,
        )
        for chunk in supporting
    )
    original_text = "\n\n".join(chunk.text for chunk in supporting)

    metadata: dict[str, object] = {"title": proposal.title}
    if proposal.topic is not None:
        metadata["topic"] = proposal.topic
    if proposal.tags:
        metadata["tags"] = proposal.tags
    if proposal.source_label is not None:
        metadata["source"] = proposal.source_label
    if proposal.importance is not None:
        metadata["importance"] = proposal.importance

    run_metadata = {
        "semantic_extraction": {
            "supporting_chunk_indexes": proposal.supporting_chunk_indexes,
            **dict(extraction_metadata),
        }
    }

    return LessonCandidate(
        text=original_text,
        provenance=CandidateProvenance(
            source_kind=first.source_kind,
            source_logical_name=first.source_logical_name,
            source_fingerprint=first.source_fingerprint,
            ingested_at=ingested_at,
            chunk_index=None,
            source_span=None,
            run_metadata=run_metadata,
            supporting_evidence=evidence,
            derivation_id=semantic_derivation_id(proposal),
        ),
        proposed_text=proposal.body,
        proposed_metadata=metadata,
        proposal_rationale=proposal.rationale,
    )


def _stable_semantic_identity(
    candidate: LessonCandidate,
) -> tuple[object, ...]:
    provenance = candidate.provenance
    return (
        candidate.candidate_id,
        candidate.text,
        candidate.proposed_text,
        candidate.proposed_metadata,
        candidate.proposal_rationale,
        provenance.source_kind,
        provenance.source_logical_name,
        provenance.source_fingerprint,
        provenance.supporting_evidence,
        provenance.derivation_id,
    )


class SemanticSourceIngestionService:
    """Stage validated semantic candidates without publication authority."""

    def __init__(self, repository: CandidateRepository) -> None:
        self._repository = repository

    def stage(
        self,
        source_fingerprint: str,
        planned: tuple[LessonCandidate, ...],
        *,
        preview: bool,
    ) -> SemanticIngestionResult:
        if type(planned) is not tuple or not all(
            type(candidate) is LessonCandidate for candidate in planned
        ):
            raise TypeError("planned must be a tuple of LessonCandidate")
        if type(preview) is not bool:
            raise TypeError("preview must be a bool")

        if not planned:
            return SemanticIngestionResult(
                source_fingerprint,
                (),
                (),
                (),
                (),
                preview,
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
            elif _stable_semantic_identity(existing) == _stable_semantic_identity(
                candidate
            ):
                skipped.append(candidate.candidate_id)
            else:
                raise IngestionConflictError(candidate.candidate_id)

        if preview:
            return SemanticIngestionResult(
                source_fingerprint,
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
                    candidate.candidate_id,
                    created_candidate_ids=created,
                ) from None
            except CandidateRepositoryError:
                remaining = tuple(item.candidate_id for item in missing[position + 1 :])
                if created:
                    raise PartialIngestionError(
                        created_candidate_ids=created,
                        failed_candidate_id=candidate.candidate_id,
                        remaining_candidate_ids=remaining,
                    ) from None
                raise IngestionStagingError(
                    "unable to stage semantic candidate",
                    failed_candidate_id=candidate.candidate_id,
                    remaining_candidate_ids=remaining,
                ) from None
            created.append(candidate.candidate_id)

        return SemanticIngestionResult(
            source_fingerprint,
            planned,
            tuple(created),
            tuple(skipped),
            (),
            False,
        )


class SemanticRawSourceIngestionService:
    """Chunk one source, extract advisory proposals, and stage candidates."""

    def __init__(
        self,
        chunker: RawSourceChunker,
        extractor: SemanticLessonExtractor,
        repository: CandidateRepository,
        clock: Callable[[], datetime] = _utc_now,
        *,
        extraction_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self._chunker = chunker
        self._extractor = extractor
        self._staging = SemanticSourceIngestionService(repository)
        self._clock = clock
        self._extraction_metadata = dict(extraction_metadata or {})

    def ingest(
        self,
        source: RawSource,
        settings: ChunkingSettings,
        *,
        preview: bool = False,
    ) -> SemanticIngestionResult:
        if type(source) is not RawSource:
            raise TypeError("source must be a RawSource")
        if type(settings) is not ChunkingSettings:
            raise TypeError("settings must be ChunkingSettings")
        if type(preview) is not bool:
            raise TypeError("preview must be a bool")

        chunks = tuple(self._chunker.chunk(source, settings))
        if not all(type(chunk) is RawSourceChunk for chunk in chunks):
            raise IngestionPlanError(
                "chunker returned an invalid semantic ingestion plan"
            )
        chunks = tuple(sorted(chunks, key=lambda chunk: chunk.index))

        for expected_index, chunk in enumerate(chunks):
            span = chunk.source_span
            if (
                chunk.index != expected_index
                or chunk.source_fingerprint != source.fingerprint
                or chunk.source_kind is not source.kind
                or chunk.source_logical_name != source.logical_name
                or span.end > len(source.content)
                or chunk.text != source.content[span.start : span.end]
            ):
                raise IngestionPlanError(
                    "chunker returned an invalid semantic ingestion plan"
                )

        try:
            extracted = self._extractor.execute(SemanticExtractionInput(chunks))
        except SemanticExtractionError:
            raise
        except Exception:
            raise SemanticExtractionError("semantic extraction failed") from None

        if type(extracted) is not SemanticLessonExtractionResult:
            raise SemanticExtractionError(
                "semantic extractor returned an invalid result"
            )

        if not chunks and extracted.proposals:
            raise SemanticExtractionError(
                "semantic extractor proposed lessons for an empty source"
            )

        ingested_at = self._clock()
        planned = tuple(
            lesson_candidate_from_semantic_proposal(
                proposal,
                chunks,
                ingested_at=ingested_at,
                extraction_metadata=self._extraction_metadata,
            )
            for proposal in extracted.proposals
        )

        if len({candidate.candidate_id for candidate in planned}) != len(planned):
            raise IngestionConflictError(None)

        return self._staging.stage(
            source.fingerprint,
            planned,
            preview=preview,
        )
