from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.candidate_review import (
    CandidateReviewConflictError,
    CandidateReviewFilter,
    CandidateReviewService,
    CandidateReviewStorageError,
    InvalidCandidateReviewInputError,
    InvalidCandidateTransitionError,
    ReviewCandidateNotFoundError,
    StaleCandidateRevisionError,
)
from lele_manager.application.lesson_candidate import (
    CandidateNotFoundError,
    CandidateProvenance,
    CandidateRepositoryError,
    CandidateReviewAction,
    CandidateRevisionConflictError,
    CandidateState,
    DuplicateCandidateIdError,
    LessonCandidate,
)
from lele_manager.application.raw_source import SourceKind


NOW = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)


def candidate(
    text: str = "source",
    *,
    state: CandidateState = CandidateState.STAGED,
    fingerprint: str = "fp-a",
    kind: SourceKind = SourceKind.MARKDOWN,
    name: str = "a.md",
    chunk: int | None = 0,
) -> LessonCandidate:
    return LessonCandidate(
        text=text,
        provenance=CandidateProvenance(
            source_kind=kind,
            source_logical_name=name,
            source_fingerprint=fingerprint,
            ingested_at=NOW,
            chunk_index=chunk,
        ),
        state=state,
    )


class MemoryRepository:
    def __init__(self, candidates: list[LessonCandidate]) -> None:
        self.items = {item.candidate_id: item for item in candidates}
        self.update_calls = 0

    def create(self, item: LessonCandidate) -> LessonCandidate:
        self.items[item.candidate_id] = item
        return item

    def get(self, candidate_id: str) -> LessonCandidate:
        try:
            return self.items[candidate_id]
        except KeyError:
            raise CandidateNotFoundError("secret adapter path") from None

    def list(self) -> tuple[LessonCandidate, ...]:
        return tuple(reversed(tuple(self.items.values())))

    def update(
        self,
        candidate_id: str,
        item: LessonCandidate,
        *,
        expected_revision: int,
    ) -> LessonCandidate:
        self.update_calls += 1
        current = self.get(candidate_id)
        if current.revision != expected_revision:
            raise CandidateRevisionConflictError("adapter race details")
        self.items[candidate_id] = item
        return item


class Clock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return NOW


def service(item: LessonCandidate) -> tuple[CandidateReviewService, MemoryRepository, Clock]:
    repository = MemoryRepository([item])
    clock = Clock()
    return CandidateReviewService(repository, clock), repository, clock


def test_revise_accept_and_reject_append_one_event_and_preserve_source() -> None:
    original = candidate()
    review, repository, clock = service(original)

    revised = review.revise_candidate(
        original.candidate_id,
        expected_revision=0,
        proposed_text="better\r\ntext",
        proposed_metadata={"topic": ["testing"]},
        reason="edited",
    )
    assert revised.text == original.text
    assert revised.provenance == original.provenance
    assert revised.state is CandidateState.STAGED
    assert revised.revision == 1
    assert revised.effective_text == "better\ntext"
    assert revised.review_history[0].action is CandidateReviewAction.REVISED

    accepted = review.accept_candidate(
        original.candidate_id, expected_revision=1, reason="ready"
    )
    assert accepted.state is CandidateState.IN_REVIEW
    assert accepted.review_history[-1].action is CandidateReviewAction.ACCEPTED

    rejected = review.reject_candidate(original.candidate_id, expected_revision=2)
    assert rejected.state is CandidateState.REJECTED
    assert rejected.review_history[-1].reason is None
    assert review.get_candidate(original.candidate_id) == rejected
    assert review.list_candidates(CandidateReviewFilter(state=CandidateState.REJECTED)) == (
        rejected,
    )
    assert repository.update_calls == 3
    assert clock.calls == 3


def test_reject_from_staged_with_reason() -> None:
    original = candidate()
    review, _, _ = service(original)
    rejected = review.reject_candidate(
        original.candidate_id, expected_revision=0, reason="not useful"
    )
    event = rejected.review_history[0]
    assert (event.previous_state, event.resulting_state, event.reason) == (
        CandidateState.STAGED,
        CandidateState.REJECTED,
        "not useful",
    )


@pytest.mark.parametrize(
    ("initial", "operation"),
    [
        (CandidateState.IN_REVIEW, "revise"),
        (CandidateState.IN_REVIEW, "accept"),
        (CandidateState.REJECTED, "revise"),
        (CandidateState.REJECTED, "reject"),
        (CandidateState.REJECTED, "accept"),
        (CandidateState.APPROVED, "revise"),
        (CandidateState.APPROVED, "accept"),
        (CandidateState.APPROVED, "reject"),
    ],
)
def test_invalid_and_repeated_transitions_are_controlled(
    initial: CandidateState, operation: str
) -> None:
    original = candidate(state=initial)
    review, repository, clock = service(original)
    with pytest.raises(InvalidCandidateTransitionError):
        if operation == "revise":
            review.revise_candidate(
                original.candidate_id,
                expected_revision=0,
                proposed_text="new",
                proposed_metadata=None,
            )
        elif operation == "accept":
            review.accept_candidate(original.candidate_id, expected_revision=0)
        else:
            review.reject_candidate(original.candidate_id, expected_revision=0)
    assert repository.update_calls == 0
    assert clock.calls == 0


def test_stale_input_is_rejected_before_clock_and_update() -> None:
    original = candidate()
    review, repository, clock = service(original)
    with pytest.raises(StaleCandidateRevisionError):
        review.accept_candidate(original.candidate_id, expected_revision=4)
    assert clock.calls == 0
    assert repository.update_calls == 0


def test_repeated_revise_is_deterministic_and_appends_exactly_once() -> None:
    original = candidate()
    review, repository, clock = service(original)
    first = review.revise_candidate(
        original.candidate_id,
        expected_revision=0,
        proposed_text="first",
        proposed_metadata={"version": 1},
    )
    second = review.revise_candidate(
        original.candidate_id,
        expected_revision=1,
        proposed_text="second\r\ntext",
        proposed_metadata={"version": 2},
    )

    assert second.effective_text == "second\ntext"
    assert second.proposed_metadata == {"version": 2}
    assert second.review_history[:-1] == first.review_history
    assert [event.revision for event in second.review_history] == [1, 2]
    assert repository.update_calls == 2
    assert clock.calls == 2


def test_repository_race_is_translated_and_sanitized() -> None:
    original = candidate()

    class RacingRepository(MemoryRepository):
        def update(self, *args: object, **kwargs: object) -> LessonCandidate:
            raise CandidateRevisionConflictError("/secret/path and adapter details")

    repository = RacingRepository([original])
    review = CandidateReviewService(repository, Clock())
    with pytest.raises(StaleCandidateRevisionError) as caught:
        review.accept_candidate(original.candidate_id, expected_revision=0)
    assert "secret" not in str(caught.value)


def test_list_is_sorted_and_all_filters_use_and_semantics() -> None:
    candidates = [
        candidate("one", fingerprint="fp-a", name="a.md", chunk=0),
        candidate(
            "two", fingerprint="fp-b", kind=SourceKind.PLAIN_TEXT,
            name="b.txt", chunk=1, state=CandidateState.REJECTED,
        ),
        candidate("three", fingerprint="fp-a", name="a.md", chunk=2),
    ]
    review = CandidateReviewService(MemoryRepository(candidates), Clock())
    assert [item.candidate_id for item in review.list_candidates()] == sorted(
        item.candidate_id for item in candidates
    )
    assert review.list_candidates(CandidateReviewFilter(state=CandidateState.REJECTED)) == (
        candidates[1],
    )
    assert review.list_candidates(CandidateReviewFilter(source_fingerprint="fp-b")) == (
        candidates[1],
    )
    assert review.list_candidates(CandidateReviewFilter(source_kind=SourceKind.PLAIN_TEXT)) == (
        candidates[1],
    )
    assert review.list_candidates(CandidateReviewFilter(source_logical_name="b.txt")) == (
        candidates[1],
    )
    assert review.list_candidates(CandidateReviewFilter(chunk_index=1)) == (candidates[1],)
    assert review.list_candidates(
        CandidateReviewFilter(source_fingerprint="fp-a", chunk_index=2)
    ) == (candidates[2],)


def test_duplicate_list_identity_is_a_controlled_conflict() -> None:
    original = candidate()
    repository = MemoryRepository([original])
    repository.list = lambda: (original, original)  # type: ignore[method-assign]
    with pytest.raises(CandidateReviewConflictError):
        CandidateReviewService(repository, Clock()).list_candidates()


@pytest.mark.parametrize(
    "filters",
    [
        lambda: object(),
        lambda: CandidateReviewFilter(source_fingerprint=""),
        lambda: CandidateReviewFilter(chunk_index=True),
    ],
)
def test_invalid_filter_input_is_controlled(filters: object) -> None:
    with pytest.raises(InvalidCandidateReviewInputError):
        value = filters() if callable(filters) else filters
        CandidateReviewService(MemoryRepository([]), Clock()).list_candidates(value)  # type: ignore[arg-type]


def test_invalid_write_input_does_not_call_clock_or_update() -> None:
    original = candidate()
    review, repository, clock = service(original)
    with pytest.raises(InvalidCandidateReviewInputError):
        review.revise_candidate(
            original.candidate_id,
            expected_revision=0,
            proposed_text="   ",
            proposed_metadata=None,
        )
    assert clock.calls == 0
    assert repository.update_calls == 0


def test_invalid_mutation_payload_does_not_retain_validation_details() -> None:
    original = candidate()
    review, repository, clock = service(original)

    with pytest.raises(InvalidCandidateReviewInputError) as caught:
        review.revise_candidate(
            original.candidate_id,
            expected_revision=0,
            proposed_text="valid",
            proposed_metadata={"private": object()},
        )

    assert caught.value.__cause__ is None
    assert "private" not in str(caught.value)
    assert repository.update_calls == 0
    assert clock.calls == 0


@pytest.mark.parametrize(
    ("candidate_id", "expected_revision", "reason"),
    [
        ("   ", 0, None),
        ("sha256:any", True, None),
        ("sha256:any", -1, None),
        ("sha256:any", 0, "   "),
        ("sha256:any", 0, "bad\ud800"),
    ],
)
def test_invalid_public_mutation_scalars_are_controlled_without_writes(
    candidate_id: str, expected_revision: object, reason: str | None
) -> None:
    original = candidate()
    repository = MemoryRepository([original])
    if candidate_id == "sha256:any":
        candidate_id = original.candidate_id
    clock = Clock()
    review = CandidateReviewService(repository, clock)

    with pytest.raises(InvalidCandidateReviewInputError):
        review.accept_candidate(
            candidate_id,
            expected_revision=expected_revision,  # type: ignore[arg-type]
            reason=reason,
        )

    assert repository.update_calls == 0
    assert clock.calls == 0


def test_missing_candidate_wins_over_invalid_mutation_payload() -> None:
    review = CandidateReviewService(MemoryRepository([]), Clock())

    with pytest.raises(ReviewCandidateNotFoundError):
        review.revise_candidate(
            "sha256:missing",
            expected_revision=0,
            proposed_text="   ",
            proposed_metadata=None,
            reason="",
        )


def test_stale_revision_wins_over_invalid_mutation_payload() -> None:
    original = candidate()
    review, repository, clock = service(original)

    with pytest.raises(StaleCandidateRevisionError):
        review.revise_candidate(
            original.candidate_id,
            expected_revision=1,
            proposed_text="   ",
            proposed_metadata=None,
            reason="",
        )

    assert repository.update_calls == 0
    assert clock.calls == 0


def test_invalid_transition_wins_over_invalid_mutation_payload() -> None:
    original = candidate(state=CandidateState.REJECTED)
    review, repository, clock = service(original)

    with pytest.raises(InvalidCandidateTransitionError):
        review.revise_candidate(
            original.candidate_id,
            expected_revision=0,
            proposed_text="   ",
            proposed_metadata=None,
            reason="",
        )

    assert repository.update_calls == 0
    assert clock.calls == 0


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (CandidateNotFoundError("/secret"), ReviewCandidateNotFoundError),
        (DuplicateCandidateIdError("/secret"), CandidateReviewConflictError),
        (CandidateRepositoryError("/secret"), CandidateReviewStorageError),
    ],
)
def test_repository_errors_are_translated_without_details(
    error: CandidateRepositoryError, expected: type[Exception]
) -> None:
    class BrokenRepository(MemoryRepository):
        def list(self) -> tuple[LessonCandidate, ...]:
            raise error

    review = CandidateReviewService(BrokenRepository([]), Clock())
    with pytest.raises(expected) as caught:
        review.list_candidates()
    assert "secret" not in str(caught.value)


def test_unexpected_programming_errors_propagate_unchanged() -> None:
    failure = RuntimeError("bug")

    class BrokenRepository(MemoryRepository):
        def list(self) -> tuple[LessonCandidate, ...]:
            raise failure

    with pytest.raises(RuntimeError) as caught:
        CandidateReviewService(BrokenRepository([]), Clock()).list_candidates()
    assert caught.value is failure


def test_review_only_changes_staging_file(tmp_path: Path) -> None:
    protected = [tmp_path / "vault.md", tmp_path / "lessons.jsonl", tmp_path / "ml.csv"]
    for path in protected:
        path.write_bytes(b"unchanged")
    repository = JsonCandidateRepository(tmp_path / "staging" / "candidates.json")
    original = repository.create(candidate())
    CandidateReviewService(repository, Clock()).accept_candidate(
        original.candidate_id, expected_revision=0
    )
    assert [path.read_bytes() for path in protected] == [b"unchanged"] * 3
