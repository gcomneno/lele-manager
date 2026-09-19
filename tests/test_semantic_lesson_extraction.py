from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Sequence

import pytest

from lele_manager.application.lesson_candidate import (
    CandidateNotFoundError,
    CandidateRevisionConflictError,
    CandidateState,
    CandidateStorageError,
    DuplicateCandidateIdError,
    LessonCandidate,
)
from lele_manager.application.raw_source import RawSource, SourceKind
from lele_manager.application.raw_source_chunking import (
    ChunkingSettings,
    DeterministicRawSourceChunker,
    RawSourceChunk,
)
from lele_manager.application.raw_source_ingestion import (
    IngestionConflictError,
    IngestionPlanError,
    IngestionStagingError,
    PartialIngestionError,
)
from lele_manager.application.semantic_lesson_extraction import (
    SemanticExtractionError,
    SemanticExtractionInput,
    SemanticIngestionResult,
    SemanticLessonExtractionResult,
    SemanticLessonProposal,
    SemanticRawSourceIngestionService,
    SemanticSourceIngestionService,
    lesson_candidate_from_semantic_proposal,
    semantic_derivation_id,
)


NOW = datetime(2026, 9, 4, 9, 30, tzinfo=timezone.utc)


class MemoryRepository:
    def __init__(self) -> None:
        self.items: dict[str, LessonCandidate] = {}
        self.list_calls = 0
        self.create_calls: list[str] = []
        self.fail_create_at: int | None = None
        self.fail_list = False

    def create(self, candidate: LessonCandidate) -> LessonCandidate:
        position = len(self.create_calls)
        self.create_calls.append(candidate.candidate_id)
        if self.fail_create_at == position:
            raise CandidateStorageError("private storage failure")
        if candidate.candidate_id in self.items:
            raise DuplicateCandidateIdError(candidate.candidate_id)
        self.items[candidate.candidate_id] = candidate
        return candidate

    def get(self, candidate_id: str) -> LessonCandidate:
        try:
            return self.items[candidate_id]
        except KeyError:
            raise CandidateNotFoundError(candidate_id) from None

    def list(self) -> Sequence[LessonCandidate]:
        self.list_calls += 1
        if self.fail_list:
            raise CandidateStorageError("private list failure")
        return tuple(self.items.values())

    def update(
        self,
        candidate_id: str,
        candidate: LessonCandidate,
        *,
        expected_revision: int,
    ) -> LessonCandidate:
        current = self.get(candidate_id)
        if current.revision != expected_revision:
            raise CandidateRevisionConflictError("stale")
        self.items[candidate_id] = candidate
        return candidate


class Extractor:
    def __init__(
        self,
        proposals: tuple[SemanticLessonProposal, ...],
    ) -> None:
        self.result = SemanticLessonExtractionResult(proposals)
        self.calls: list[SemanticExtractionInput] = []

    def execute(
        self,
        value: SemanticExtractionInput,
    ) -> SemanticLessonExtractionResult:
        self.calls.append(value)
        return self.result


def source() -> RawSource:
    return RawSource(
        "# Reliability\n\nValidate at boundaries.\n\n"
        "Keep authority in application code.\n",
        SourceKind.MARKDOWN,
        "notes.md",
    )


def chunks() -> tuple[RawSourceChunk, ...]:
    return DeterministicRawSourceChunker().chunk(
        source(),
        ChunkingSettings(max_characters=28),
    )


def proposal(
    *,
    title: str = "Validate boundaries",
    body: str = "Validate untrusted data at the authority boundary.",
    rationale: str = "The source explicitly recommends validation at boundaries.",
    supporting: tuple[int, ...] = (1,),
) -> SemanticLessonProposal:
    return SemanticLessonProposal(
        title=title,
        body=body,
        rationale=rationale,
        supporting_chunk_indexes=supporting,
        topic="architecture",
        tags=("validation", "boundaries"),
        source_label="engineering-notes",
        importance=4,
    )


def service(
    repository: MemoryRepository,
    proposals: tuple[SemanticLessonProposal, ...],
) -> SemanticRawSourceIngestionService:
    return SemanticRawSourceIngestionService(
        DeterministicRawSourceChunker(),
        Extractor(proposals),
        repository,
        lambda: NOW,
        extraction_metadata={
            "strategy": "semantic",
            "provider": "test",
            "model": "fixture",
            "locality": "local",
        },
    )


def test_semantic_input_requires_one_ordered_source() -> None:
    selected = chunks()

    assert SemanticExtractionInput(selected).chunks == selected
    assert SemanticExtractionInput(()).chunks == ()

    with pytest.raises(ValueError, match="ascending"):
        SemanticExtractionInput(tuple(reversed(selected)))

    with pytest.raises(ValueError, match="unique"):
        SemanticExtractionInput((selected[0], selected[0]))


def test_semantic_result_supports_zero_one_or_many_proposals() -> None:
    one = proposal()
    another = proposal(
        title="Keep authority explicit",
        body="Inference must not become mutation authority.",
        supporting=(2,),
    )

    assert SemanticLessonExtractionResult(()).proposals == ()
    assert SemanticLessonExtractionResult((one,)).proposals == (one,)
    assert SemanticLessonExtractionResult((one, another)).proposals == (
        one,
        another,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"body": ""},
        {"rationale": "\t"},
        {"supporting_chunk_indexes": ()},
        {"supporting_chunk_indexes": (1, 1)},
        {"supporting_chunk_indexes": (2, 1)},
        {"importance": 0},
        {"importance": 6},
    ],
)
def test_invalid_semantic_proposals_fail_closed(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "title": "Title",
        "body": "Body",
        "rationale": "Reason",
        "supporting_chunk_indexes": (0,),
        "topic": None,
        "tags": (),
        "source_label": None,
        "importance": None,
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError)):
        SemanticLessonProposal(**values)  # type: ignore[arg-type]


def test_mapper_reconstructs_exact_supporting_evidence_and_advisory_fields() -> None:
    selected = chunks()
    item = proposal(
        supporting=(1, 2),
    )

    candidate = lesson_candidate_from_semantic_proposal(
        item,
        selected,
        ingested_at=NOW,
        extraction_metadata={
            "strategy": "semantic",
            "provider": "ollama",
            "model": "fixture",
        },
    )

    assert candidate.text == f"{selected[1].text}\n\n{selected[2].text}"
    assert candidate.proposed_text == item.body
    assert candidate.proposal_rationale == item.rationale
    assert candidate.proposed_metadata == {
        "title": item.title,
        "topic": "architecture",
        "tags": ("validation", "boundaries"),
        "source": "engineering-notes",
        "importance": 4,
    }
    assert candidate.provenance.chunk_index is None
    assert candidate.provenance.source_span is None
    assert tuple(
        evidence.chunk_index for evidence in candidate.provenance.supporting_evidence
    ) == (1, 2)
    assert tuple(
        evidence.source_span for evidence in candidate.provenance.supporting_evidence
    ) == (
        selected[1].source_span,
        selected[2].source_span,
    )
    assert candidate.provenance.derivation_id == semantic_derivation_id(item)
    assert candidate.provenance.run_metadata["semantic_extraction"] == {
        "supporting_chunk_indexes": (1, 2),
        "strategy": "semantic",
        "provider": "ollama",
        "model": "fixture",
    }


def test_mapper_rejects_unknown_supporting_chunk() -> None:
    with pytest.raises(SemanticExtractionError, match="unknown source chunk"):
        lesson_candidate_from_semantic_proposal(
            proposal(supporting=(999,)),
            chunks(),
            ingested_at=NOW,
            extraction_metadata={},
        )


def test_derivation_id_is_stable_across_diagnostic_metadata_and_timestamp() -> None:
    selected = chunks()
    item = proposal()

    first = lesson_candidate_from_semantic_proposal(
        item,
        selected,
        ingested_at=NOW,
        extraction_metadata={"model": "one"},
    )
    second = lesson_candidate_from_semantic_proposal(
        item,
        selected,
        ingested_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        extraction_metadata={"model": "two"},
    )

    assert first.provenance.derivation_id == second.provenance.derivation_id
    assert first.candidate_id == second.candidate_id


def test_distinct_lessons_from_same_evidence_have_distinct_derivations() -> None:
    selected = chunks()
    first = proposal(
        title="First",
        body="First supported lesson.",
    )
    second = proposal(
        title="Second",
        body="Second supported lesson.",
    )

    assert semantic_derivation_id(first) != semantic_derivation_id(second)

    first_candidate = lesson_candidate_from_semantic_proposal(
        first,
        selected,
        ingested_at=NOW,
        extraction_metadata={},
    )
    second_candidate = lesson_candidate_from_semantic_proposal(
        second,
        selected,
        ingested_at=NOW,
        extraction_metadata={},
    )
    assert first_candidate.candidate_id != second_candidate.candidate_id


def test_preview_is_read_only_and_zero_result_does_not_even_read_repository() -> None:
    repository = MemoryRepository()

    zero = service(repository, ()).ingest(
        source(),
        ChunkingSettings(max_characters=28),
        preview=True,
    )

    assert zero == SemanticIngestionResult(
        source().fingerprint,
        (),
        (),
        (),
        (),
        True,
    )
    assert repository.list_calls == 0
    assert repository.create_calls == []


def test_preview_plans_without_creating_and_stage_creates_once() -> None:
    repository = MemoryRepository()
    semantic = service(repository, (proposal(),))

    preview = semantic.ingest(
        source(),
        ChunkingSettings(max_characters=28),
        preview=True,
    )
    assert preview.created_count == 0
    assert preview.pending_count == 1
    assert repository.items == {}

    staged = semantic.ingest(
        source(),
        ChunkingSettings(max_characters=28),
        preview=False,
    )
    assert staged.created_count == 1
    assert staged.pending_count == 0
    assert len(repository.items) == 1


def test_replay_skips_stable_semantic_candidate() -> None:
    repository = MemoryRepository()
    semantic = service(repository, (proposal(),))

    first = semantic.ingest(
        source(),
        ChunkingSettings(max_characters=28),
    )
    replay = semantic.ingest(
        source(),
        ChunkingSettings(max_characters=28),
    )

    assert first.created_count == 1
    assert replay.created_count == 0
    assert replay.skipped_candidate_ids == first.candidate_ids


def test_conflicting_existing_candidate_fails_closed() -> None:
    repository = MemoryRepository()
    semantic = service(repository, (proposal(),))

    first = semantic.ingest(
        source(),
        ChunkingSettings(max_characters=28),
    )
    stored = repository.get(first.candidate_ids[0])
    repository.items[stored.candidate_id] = replace(
        stored,
        proposal_rationale="different rationale",
    )

    with pytest.raises(IngestionConflictError):
        semantic.ingest(
            source(),
            ChunkingSettings(max_characters=28),
        )


def test_initial_repository_failure_is_controlled() -> None:
    repository = MemoryRepository()
    repository.fail_list = True

    with pytest.raises(IngestionStagingError):
        service(repository, (proposal(),)).ingest(
            source(),
            ChunkingSettings(max_characters=28),
        )


def test_partial_failure_reports_created_failed_and_remaining_candidates() -> None:
    proposals = (
        proposal(
            title="One",
            body="One supported lesson.",
            supporting=(1,),
        ),
        proposal(
            title="Two",
            body="Two supported lesson.",
            supporting=(2,),
        ),
        proposal(
            title="Three",
            body="Three supported lesson.",
            supporting=(3,),
        ),
    )

    expected = service(MemoryRepository(), proposals).ingest(
        source(),
        ChunkingSettings(max_characters=28),
        preview=True,
    )

    repository = MemoryRepository()
    repository.fail_create_at = 1
    semantic = service(repository, proposals)

    with pytest.raises(PartialIngestionError) as caught:
        semantic.ingest(
            source(),
            ChunkingSettings(max_characters=28),
        )

    error = caught.value
    assert error.created_candidate_ids == (expected.candidate_ids[0],)
    assert error.failed_candidate_id == expected.candidate_ids[1]
    assert error.remaining_candidate_ids == (expected.candidate_ids[2],)
    assert repository.create_calls == list(expected.candidate_ids[:2])


def test_extraction_failure_never_reads_or_writes_repository() -> None:
    class FailingExtractor:
        def execute(
            self,
            value: SemanticExtractionInput,
        ) -> SemanticLessonExtractionResult:
            raise SemanticExtractionError("backend failed")

    repository = MemoryRepository()
    semantic = SemanticRawSourceIngestionService(
        DeterministicRawSourceChunker(),
        FailingExtractor(),
        repository,
        lambda: NOW,
    )

    with pytest.raises(SemanticExtractionError, match="backend failed"):
        semantic.ingest(
            source(),
            ChunkingSettings(max_characters=28),
        )

    assert repository.list_calls == 0
    assert repository.create_calls == []


def test_empty_source_with_zero_proposals_is_valid() -> None:
    repository = MemoryRepository()

    result = service(repository, ()).ingest(
        RawSource("", SourceKind.PLAIN_TEXT, "empty.txt"),
        ChunkingSettings(),
        preview=False,
    )

    assert result.planned_candidates == ()
    assert repository.list_calls == 0


def test_empty_source_cannot_receive_a_semantic_proposal() -> None:
    repository = MemoryRepository()

    with pytest.raises(
        SemanticExtractionError,
        match="empty source",
    ):
        service(repository, (proposal(supporting=(0,)),)).ingest(
            RawSource("", SourceKind.PLAIN_TEXT, "empty.txt"),
            ChunkingSettings(),
        )


def test_invalid_chunk_plan_fails_before_extraction_or_staging() -> None:
    raw = source()
    valid = chunks()[0]
    invalid = replace(
        valid,
        source_fingerprint="sha256:wrong",
    )

    class InvalidChunker:
        def chunk(
            self,
            source: RawSource,
            settings: ChunkingSettings,
        ) -> Sequence[RawSourceChunk]:
            return (invalid,)

    extractor = Extractor(())
    repository = MemoryRepository()
    semantic = SemanticRawSourceIngestionService(
        InvalidChunker(),
        extractor,
        repository,
        lambda: NOW,
    )

    with pytest.raises(IngestionPlanError):
        semantic.ingest(
            raw,
            ChunkingSettings(),
        )

    assert extractor.calls == []
    assert repository.list_calls == 0


def test_extractor_must_return_exact_semantic_result_type() -> None:
    class BadExtractor:
        def execute(self, value: SemanticExtractionInput) -> object:
            return object()

    repository = MemoryRepository()
    semantic = SemanticRawSourceIngestionService(
        DeterministicRawSourceChunker(),
        BadExtractor(),  # type: ignore[arg-type]
        repository,
        lambda: NOW,
    )

    with pytest.raises(
        SemanticExtractionError,
        match="invalid result",
    ):
        semantic.ingest(
            source(),
            ChunkingSettings(max_characters=28),
        )

    assert repository.list_calls == 0


def test_staging_service_does_not_touch_canonical_authority() -> None:
    repository = MemoryRepository()
    selected = chunks()
    candidate = lesson_candidate_from_semantic_proposal(
        proposal(),
        selected,
        ingested_at=NOW,
        extraction_metadata={"strategy": "semantic"},
    )

    staged = SemanticSourceIngestionService(repository).stage(
        source().fingerprint,
        (candidate,),
        preview=False,
    )

    assert staged.created_count == 1
    assert repository.get(candidate.candidate_id).state is CandidateState.STAGED
