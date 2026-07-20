from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pytest

from lele_manager.application.lesson_candidate import (
    CandidateState,
    CandidateStorageError,
    DuplicateCandidateIdError,
    LessonCandidate,
)
from lele_manager.application.raw_source import RawSource, SourceKind, SourceSpan
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
    RawSourceIngestionResult,
    RawSourceIngestionService,
)


NOW = datetime(2026, 7, 20, 9, 30, tzinfo=timezone.utc)


class MemoryRepository:
    def __init__(self, candidates: Sequence[LessonCandidate] = ()) -> None:
        self.candidates = {item.candidate_id: item for item in candidates}
        self.list_calls = 0
        self.create_calls: list[str] = []
        self.fail_list = False
        self.fail_create_at: int | None = None

    def list(self) -> tuple[LessonCandidate, ...]:
        self.list_calls += 1
        if self.fail_list:
            raise CandidateStorageError("secret adapter detail")
        return tuple(self.candidates.values())

    def create(self, candidate: LessonCandidate) -> LessonCandidate:
        attempt = len(self.create_calls)
        self.create_calls.append(candidate.candidate_id)
        if self.fail_create_at == attempt:
            raise CandidateStorageError("secret adapter path")
        if candidate.candidate_id in self.candidates:
            raise DuplicateCandidateIdError("concurrent duplicate")
        self.candidates[candidate.candidate_id] = candidate
        return candidate

    def get(self, candidate_id: str) -> LessonCandidate:
        return self.candidates[candidate_id]

    def update(
        self, candidate_id: str, candidate: LessonCandidate
    ) -> LessonCandidate:
        self.candidates[candidate_id] = candidate
        return candidate


class Clock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return NOW


def source() -> RawSource:
    return RawSource(
        "# First\n\nalpha\n\n## Second\n\nbeta",
        SourceKind.MARKDOWN,
        "inbox.md",
    )


def service(repository: MemoryRepository, clock: Clock | None = None) -> RawSourceIngestionService:
    return RawSourceIngestionService(
        DeterministicRawSourceChunker(), repository, clock or Clock()
    )


def test_plans_in_chunk_order_with_complete_exact_provenance() -> None:
    repository = MemoryRepository()
    clock = Clock()
    raw = source()
    settings = ChunkingSettings(max_characters=19)

    result = service(repository, clock).ingest(raw, settings)

    assert clock.calls == 1
    assert result.candidate_ids == result.created_candidate_ids
    assert [item.provenance.chunk_index for item in result.planned_candidates] == [0, 1]
    for candidate in result.planned_candidates:
        provenance = candidate.provenance
        assert provenance.source_kind is raw.kind
        assert provenance.source_logical_name == raw.logical_name
        assert provenance.source_fingerprint == raw.fingerprint
        assert provenance.ingested_at is NOW
        assert candidate.text == raw.content[
            provenance.source_span.start : provenance.source_span.end  # type: ignore[union-attr]
        ]
        assert provenance.run_metadata["chunking"] == {
            "max_characters": 19,
            "heading_context": ("First",)
            if provenance.chunk_index == 0
            else ("First", "Second"),
        }
        assert candidate.proposed_metadata is None


def test_identical_rerun_skips_and_preserves_review_data() -> None:
    repository = MemoryRepository()
    settings = ChunkingSettings(max_characters=19)
    first = service(repository).ingest(source(), settings)
    original = repository.candidates[first.candidate_ids[0]]
    reviewed = replace(
        original,
        state=CandidateState.IN_REVIEW,
        proposed_metadata={"topic": "kept"},
    )
    repository.candidates[reviewed.candidate_id] = reviewed

    rerun = service(repository).ingest(source(), settings)

    assert rerun.created_candidate_ids == ()
    assert rerun.skipped_candidate_ids == first.candidate_ids
    assert repository.candidates[reviewed.candidate_id] is reviewed
    assert repository.create_calls == list(first.candidate_ids)


def test_preview_has_same_plan_without_writes_and_classifies_ids() -> None:
    settings = ChunkingSettings(max_characters=19)
    baseline_repository = MemoryRepository()
    baseline = service(baseline_repository).ingest(source(), settings, preview=True)
    existing = baseline.planned_candidates[0]
    repository = MemoryRepository((existing,))

    preview = service(repository).ingest(source(), settings, preview=True)
    real_plan = service(MemoryRepository()).ingest(source(), settings)

    assert preview.candidate_ids == real_plan.candidate_ids
    assert preview.skipped_candidate_ids == (preview.candidate_ids[0],)
    assert preview.pending_candidate_ids == preview.candidate_ids[1:]
    assert preview.created_candidate_ids == ()
    assert repository.create_calls == []


def test_empty_input_calls_clock_once_and_never_inspects_or_writes() -> None:
    repository = MemoryRepository()
    clock = Clock()

    result = service(repository, clock).ingest(
        RawSource(" \n", SourceKind.PLAIN_TEXT, "empty"),
        ChunkingSettings(max_characters=2),
    )

    assert clock.calls == 1
    assert repository.list_calls == 0
    assert repository.create_calls == []
    assert result.candidate_ids == ()
    assert (result.created_count, result.skipped_count, result.pending_count) == (0, 0, 0)


def test_repository_list_failure_is_sanitized() -> None:
    repository = MemoryRepository()
    repository.fail_list = True

    with pytest.raises(IngestionStagingError) as caught:
        service(repository).ingest(source(), ChunkingSettings(max_characters=19))

    assert "secret" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_create_failure_before_first_write_is_controlled() -> None:
    repository = MemoryRepository()
    repository.fail_create_at = 0

    with pytest.raises(IngestionStagingError) as caught:
        service(repository).ingest(source(), ChunkingSettings(max_characters=19))

    assert caught.value.failed_candidate_id is not None
    assert len(caught.value.remaining_candidate_ids) == 1
    assert repository.candidates == {}


def test_partial_failure_is_ordered_and_rerun_completes_missing_candidates() -> None:
    repository = MemoryRepository()
    repository.fail_create_at = 1
    ingestion = service(repository)

    with pytest.raises(PartialIngestionError) as caught:
        ingestion.ingest(source(), ChunkingSettings(max_characters=19))

    error = caught.value
    assert error.created_candidate_ids == tuple(repository.candidates)
    assert error.failed_candidate_id == repository.create_calls[1]
    assert error.remaining_candidate_ids == ()

    repository.fail_create_at = None
    completed = service(repository).ingest(source(), ChunkingSettings(max_characters=19))
    assert completed.skipped_candidate_ids == error.created_candidate_ids
    assert completed.created_candidate_ids == (error.failed_candidate_id,)


def test_incompatible_forced_id_collision_conflicts_before_writes() -> None:
    repository = MemoryRepository()
    plan = service(repository).ingest(
        source(), ChunkingSettings(max_characters=19), preview=True
    )
    collision = replace(
        plan.planned_candidates[0],
        provenance=replace(
            plan.planned_candidates[0].provenance,
            source_span=SourceSpan(100, 100 + len(plan.planned_candidates[0].text)),
        ),
    )
    object.__setattr__(collision, "candidate_id", plan.candidate_ids[0])
    repository = MemoryRepository((collision,))

    with pytest.raises(IngestionConflictError) as caught:
        service(repository).ingest(source(), ChunkingSettings(max_characters=19))

    assert caught.value.candidate_id == plan.candidate_ids[0]
    assert repository.create_calls == []


def test_duplicate_during_create_is_a_conflict_with_prior_creates() -> None:
    class ConcurrentRepository(MemoryRepository):
        def create(self, candidate: LessonCandidate) -> LessonCandidate:
            if len(self.create_calls) == 1:
                self.create_calls.append(candidate.candidate_id)
                raise DuplicateCandidateIdError("race detail")
            return super().create(candidate)

    repository = ConcurrentRepository()
    with pytest.raises(IngestionConflictError) as caught:
        service(repository).ingest(source(), ChunkingSettings(max_characters=19))

    assert caught.value.created_candidate_ids == (repository.create_calls[0],)
    assert "race" not in str(caught.value)


def test_result_is_immutable_and_rejects_inconsistent_values() -> None:
    result = service(MemoryRepository()).ingest(
        source(), ChunkingSettings(max_characters=19), preview=True
    )
    with pytest.raises(FrozenInstanceError):
        result.preview = False  # type: ignore[misc]
    with pytest.raises(ValueError, match="disjoint"):
        RawSourceIngestionResult(
            result.source_fingerprint,
            result.planned_candidates,
            (),
            (result.candidate_ids[0],),
            result.candidate_ids,
            True,
        )


def test_result_defensively_freezes_mutable_sequences() -> None:
    plan = service(MemoryRepository()).ingest(
        source(), ChunkingSettings(max_characters=19), preview=True
    )
    candidates = list(plan.planned_candidates)
    pending = list(plan.candidate_ids)
    result = RawSourceIngestionResult(
        plan.source_fingerprint, candidates, [], [], pending, True
    )

    candidates.clear()
    pending.reverse()

    assert isinstance(result.planned_candidates, tuple)
    assert isinstance(result.created_candidate_ids, tuple)
    assert isinstance(result.skipped_candidate_ids, tuple)
    assert isinstance(result.pending_candidate_ids, tuple)
    assert result.candidate_ids == plan.candidate_ids
    assert result.pending_candidate_ids == plan.candidate_ids


def test_result_rejects_reversed_status_order_and_foreign_fingerprint() -> None:
    plan = service(MemoryRepository()).ingest(
        source(), ChunkingSettings(max_characters=19), preview=True
    )
    with pytest.raises(ValueError, match="preserve plan order"):
        RawSourceIngestionResult(
            plan.source_fingerprint,
            plan.planned_candidates,
            (),
            (),
            tuple(reversed(plan.candidate_ids)),
            True,
        )
    with pytest.raises(ValueError, match="fingerprints"):
        RawSourceIngestionResult(
            "sha256:foreign",
            plan.planned_candidates,
            (),
            (),
            plan.candidate_ids,
            True,
        )


class FixedChunker:
    def __init__(self, chunks: Sequence[object]) -> None:
        self.chunks = chunks

    def chunk(
        self, raw: RawSource, settings: ChunkingSettings
    ) -> Sequence[RawSourceChunk]:
        return self.chunks  # type: ignore[return-value]


def chunks_for(raw: RawSource) -> tuple[RawSourceChunk, ...]:
    return DeterministicRawSourceChunker().chunk(
        raw, ChunkingSettings(max_characters=19)
    )


def test_reversed_chunk_output_is_normalized_into_index_order() -> None:
    raw = source()
    repository = MemoryRepository()
    result = RawSourceIngestionService(
        FixedChunker(tuple(reversed(chunks_for(raw)))), repository, Clock()
    ).ingest(raw, ChunkingSettings(max_characters=19))

    assert [candidate.provenance.chunk_index for candidate in result.planned_candidates] == [0, 1]
    assert result.created_candidate_ids == result.candidate_ids


@pytest.mark.parametrize(
    "bad_indexes",
    [(0, 0), (0, 2)],
    ids=["duplicate", "non-contiguous"],
)
def test_invalid_chunk_indexes_fail_before_repository_inspection(
    bad_indexes: tuple[int, int],
) -> None:
    raw = source()
    repository = MemoryRepository()
    chunks = tuple(
        replace(chunk, index=index)
        for chunk, index in zip(chunks_for(raw), bad_indexes, strict=True)
    )

    with pytest.raises(IngestionPlanError):
        RawSourceIngestionService(FixedChunker(chunks), repository, Clock()).ingest(
            raw, ChunkingSettings(max_characters=19)
        )

    assert repository.list_calls == 0
    assert repository.create_calls == []


@pytest.mark.parametrize("defect", ["fingerprint", "text"])
def test_foreign_or_inexact_chunk_is_rejected_before_repository_inspection(
    defect: str,
) -> None:
    raw = source()
    repository = MemoryRepository()
    first, second = chunks_for(raw)
    if defect == "fingerprint":
        first = replace(first, source_fingerprint="sha256:foreign")
    else:
        replacement = "X" + first.text[1:]
        first = replace(first, text=replacement)

    with pytest.raises(IngestionPlanError):
        RawSourceIngestionService(
            FixedChunker((first, second)), repository, Clock()
        ).ingest(raw, ChunkingSettings(max_characters=19))

    assert repository.list_calls == 0


def test_duplicate_from_repository_list_is_sanitized_conflict() -> None:
    class DuplicateListingRepository(MemoryRepository):
        def list(self) -> tuple[LessonCandidate, ...]:
            self.list_calls += 1
            raise DuplicateCandidateIdError("secret duplicate detail")

    repository = DuplicateListingRepository()
    with pytest.raises(IngestionConflictError) as caught:
        service(repository).ingest(source(), ChunkingSettings(max_characters=19))

    assert caught.value.candidate_id is None
    assert "secret" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_module_has_no_forbidden_imports_and_protected_files_are_unchanged(
    tmp_path: Path,
) -> None:
    module = Path(__file__).parents[1] / "src/lele_manager/application/raw_source_ingestion.py"
    text = module.read_text(encoding="utf-8").lower()
    forbidden = ("fastapi", ".cli", "vault", "projection", "export", ".ml", "llm")
    assert not any(term in text for term in forbidden)

    protected = {
        tmp_path / "vault.md": b"vault",
        tmp_path / "projection.jsonl": b"projection",
        tmp_path / "export.json": b"export",
        tmp_path / "training.csv": b"ml",
    }
    for path, contents in protected.items():
        path.write_bytes(contents)
    service(MemoryRepository()).ingest(source(), ChunkingSettings(max_characters=19))
    assert {path: path.read_bytes() for path in protected} == protected


def test_unexpected_non_repository_errors_are_not_mislabeled() -> None:
    class BrokenRepository(MemoryRepository):
        def list(self) -> tuple[LessonCandidate, ...]:
            raise RuntimeError("programming error")

    with pytest.raises(RuntimeError, match="programming error"):
        service(BrokenRepository()).ingest(source(), ChunkingSettings(max_characters=19))
