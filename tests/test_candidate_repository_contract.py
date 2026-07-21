from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from lele_manager.adapters import json_candidate_repository as json_adapter
from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.lesson_candidate import (
    CandidateNotFoundError,
    CandidateProvenance,
    CandidateRepository,
    CandidateReviewAction,
    CandidateReviewEvent,
    CandidateRevisionConflictError,
    CandidateState,
    CandidateStorageError,
    DuplicateCandidateIdError,
    ImmutableCandidateFieldError,
    LessonCandidate,
    MalformedStagingDataError,
    SourceSpan,
)
from lele_manager.application.raw_source import SourceKind


@pytest.fixture(params=["json"])
def repository_factory(
    request: pytest.FixtureRequest,
) -> Callable[[Path], CandidateRepository]:
    assert request.param == "json"
    return JsonCandidateRepository


def candidate(text: str, *, chunk_index: int = 0) -> LessonCandidate:
    return LessonCandidate(
        text,
        CandidateProvenance(
            source_kind=SourceKind.MARKDOWN,
            source_logical_name="inbox.md",
            source_fingerprint="sha256:raw-source",
            ingested_at=datetime(2026, 7, 19, 12, 30, tzinfo=timezone.utc),
            chunk_index=chunk_index,
            source_span=SourceSpan(chunk_index * 10, chunk_index * 10 + len(text)),
            run_metadata={"batch": "local-1"},
            transformations=({"kind": "manual-cleanup"},),
        ),
        proposed_metadata={"topic": "architecture", "importance": 4},
    )


def mutated(
    original: LessonCandidate,
    *,
    state: CandidateState = CandidateState.IN_REVIEW,
    proposed_metadata: dict[str, object] | None = None,
    provenance: CandidateProvenance | None = None,
    text: str | None = None,
) -> LessonCandidate:
    action = (
        CandidateReviewAction.REJECTED
        if state is CandidateState.REJECTED
        else CandidateReviewAction.ACCEPTED
    )
    event = CandidateReviewEvent(
        revision=1,
        action=action,
        occurred_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        previous_state=CandidateState.STAGED,
        resulting_state=state,
    )
    return replace(
        original,
        text=original.text if text is None else text,
        provenance=original.provenance if provenance is None else provenance,
        proposed_metadata=proposed_metadata,
        state=state,
        revision=1,
        review_history=(event,),
    )


def schema_v1_record(item: LessonCandidate) -> dict[str, object]:
    provenance = item.provenance
    span = provenance.source_span
    return {
        "candidate_id": item.candidate_id,
        "proposed_metadata": {"legacy": ["kept", {"nested": True}]},
        "provenance": {
            "chunk_index": provenance.chunk_index,
            "ingested_at": provenance.ingested_at.isoformat(),
            "run_metadata": {"legacy_run": [1, 2]},
            "source_fingerprint": provenance.source_fingerprint,
            "source_kind": provenance.source_kind.value,
            "source_logical_name": provenance.source_logical_name,
            "source_span": (
                None if span is None else {"end": span.end, "start": span.start}
            ),
            "transformations": [{"kind": "legacy-transform"}],
        },
        "state": item.state.value,
        "text": item.text,
    }


def write_schema_v1(path: Path, items: list[LessonCandidate]) -> bytes:
    document = {
        "candidates": [schema_v1_record(item) for item in items],
        "schema_version": 1,
    }
    contents = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode()
    path.write_bytes(contents)
    return contents


def test_missing_storage_is_empty_and_missing_get_is_controlled(
    tmp_path: Path, repository_factory: Callable[[Path], CandidateRepository]
) -> None:
    repository = repository_factory(tmp_path / "missing" / "candidates.json")

    assert repository.list() == ()
    with pytest.raises(CandidateNotFoundError, match="missing"):
        repository.get("missing")


def test_create_get_list_and_update_lifecycle_and_metadata(
    tmp_path: Path, repository_factory: Callable[[Path], CandidateRepository]
) -> None:
    repository = repository_factory(tmp_path / "candidates.json")
    original = candidate("review me")

    assert repository.create(original) == original
    assert repository.get(original.candidate_id) == original

    updated = mutated(original, proposed_metadata={"topic": "revised"})
    assert repository.update(
        original.candidate_id, updated, expected_revision=0
    ) == updated
    assert repository.get(original.candidate_id) == updated


def test_nested_metadata_round_trip_is_logically_preserved(
    tmp_path: Path, repository_factory: Callable[[Path], CandidateRepository]
) -> None:
    path = tmp_path / "candidates.json"
    repository = repository_factory(path)
    original = replace(
        candidate("nested"),
        proposed_metadata={"labels": ["one", {"nested": [1, 2]}]},
    )

    repository.create(original)

    assert repository.get(original.candidate_id) == original
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["candidates"][0]["proposed_metadata"] == {
        "labels": ["one", {"nested": [1, 2]}]
    }


def test_valid_unicode_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    original = replace(
        candidate("Lezione caffè 😀 \U00020000"),
        proposed_metadata={"città": ["Perché", "😀", "\U00020000"]},
    )

    JsonCandidateRepository(path).create(original)

    assert JsonCandidateRepository(path).get(original.candidate_id) == original
    assert "Lezione caffè 😀 \U00020000" in path.read_text(encoding="utf-8")


def test_create_collision_never_overwrites(
    tmp_path: Path, repository_factory: Callable[[Path], CandidateRepository]
) -> None:
    repository = repository_factory(tmp_path / "candidates.json")
    original = candidate("same")
    repository.create(original)

    with pytest.raises(DuplicateCandidateIdError, match="duplicate candidate id"):
        repository.create(replace(original, state=CandidateState.REJECTED))

    assert repository.get(original.candidate_id).state is CandidateState.STAGED


def test_update_missing_and_immutable_fields_are_controlled(
    tmp_path: Path, repository_factory: Callable[[Path], CandidateRepository]
) -> None:
    repository = repository_factory(tmp_path / "candidates.json")
    original = candidate("same")
    repository.create(original)
    later_provenance = replace(
        original.provenance,
        ingested_at=original.provenance.ingested_at + timedelta(seconds=1),
    )

    with pytest.raises(ImmutableCandidateFieldError, match="immutable"):
        repository.update(
            original.candidate_id,
            mutated(original, provenance=later_provenance),
            expected_revision=0,
        )
    with pytest.raises(ImmutableCandidateFieldError, match="immutable"):
        repository.update(
            original.candidate_id,
            mutated(original, text="different"),
            expected_revision=0,
        )
    changed_source = replace(original.provenance, source_logical_name="elsewhere.md")
    with pytest.raises(ImmutableCandidateFieldError, match="immutable"):
        repository.update(
            original.candidate_id,
            mutated(original, provenance=changed_source),
            expected_revision=0,
        )
    with pytest.raises(CandidateNotFoundError):
        repository.update(
            "sha256:genuinely-missing", mutated(original), expected_revision=0
        )


def test_aware_timestamp_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    original = candidate("aware")

    JsonCandidateRepository(path).create(original)

    loaded = JsonCandidateRepository(path).get(original.candidate_id)
    assert loaded.provenance.ingested_at == original.provenance.ingested_at
    assert loaded.provenance.ingested_at.utcoffset() is not None


def test_explicit_empty_document_and_deterministic_order_and_bytes(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty.json"
    empty_path.write_text('{"candidates":[],"schema_version":1}\n', encoding="utf-8")
    assert JsonCandidateRepository(empty_path).list() == ()

    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_repository = JsonCandidateRepository(first_path)
    second_repository = JsonCandidateRepository(second_path)
    candidates = [candidate("z", chunk_index=1), candidate("a", chunk_index=0)]
    for item in candidates:
        first_repository.create(item)
    for item in reversed(candidates):
        second_repository.create(item)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert [item.candidate_id for item in first_repository.list()] == sorted(
        item.candidate_id for item in candidates
    )


@pytest.mark.parametrize(
    "contents",
    [
        "",
        "not json",
        "[]",
        '{"schema_version":3,"candidates":[]}',
        '{"schema_version":1,"candidates":{}}',
        '{"schema_version":1,"candidates":[{}]}',
        '{"schema_version":true,"candidates":[]}',
        '{"schema_version":1,"candidates":[],"unknown":null}',
        '{"schema_version":1}',
        '{"schema_version":1,"schema_version":1,"candidates":[]}',
        '{"schema_version":1,"candidates":[],"value":NaN}',
        '{"schema_version":1,"candidates":[],"value":Infinity}',
        '{"schema_version":1,"candidates":[],"value":-Infinity}',
    ],
)
def test_malformed_storage_is_a_controlled_error(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "candidates.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(MalformedStagingDataError):
        JsonCandidateRepository(path).list()


def test_duplicate_ids_in_persisted_data_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    repository.create(candidate("duplicate"))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["candidates"].append(document["candidates"][0])
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(DuplicateCandidateIdError, match="duplicate candidate id"):
        repository.list()


def test_tampered_candidate_id_is_malformed(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    repository.create(candidate("original"))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["candidates"][0]["candidate_id"] = "sha256:tampered"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MalformedStagingDataError, match="invalid ID"):
        repository.list()


def test_escaped_surrogate_in_persisted_json_is_malformed(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    repository.create(candidate("original"))
    contents = path.read_text(encoding="utf-8").replace("original", r"escaped \ud800")
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(MalformedStagingDataError, match="malformed"):
        repository.list()


@pytest.mark.parametrize("level", ["candidate", "provenance", "source_span"])
@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_nested_schema_requires_exact_fields(
    tmp_path: Path, level: str, mutation: str
) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    original = candidate("schema")
    repository.create(original)
    document = json.loads(path.read_text(encoding="utf-8"))
    candidate_data = document["candidates"][0]
    targets = {
        "candidate": (candidate_data, "state"),
        "provenance": (candidate_data["provenance"], "run_metadata"),
        "source_span": (candidate_data["provenance"]["source_span"], "start"),
    }
    target, required = targets[level]
    if mutation == "missing":
        del target[required]
    else:
        target["unknown"] = None
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MalformedStagingDataError):
        repository.list()


def test_storage_failures_are_controlled_and_do_not_leak_paths(tmp_path: Path) -> None:
    directory_as_file = tmp_path / "storage"
    directory_as_file.mkdir()
    repository = JsonCandidateRepository(directory_as_file)

    with pytest.raises(CandidateStorageError, match="read staging storage") as caught:
        repository.list()
    assert str(directory_as_file) not in str(caught.value)
    assert caught.value.__cause__ is None

    blocked_parent = tmp_path / "parent-is-a-file"
    blocked_parent.write_text("x", encoding="utf-8")
    with pytest.raises(CandidateStorageError, match="write staging storage") as caught:
        JsonCandidateRepository(blocked_parent / "candidates.json").create(candidate("x"))
    assert str(blocked_parent) not in str(caught.value)
    assert caught.value.__cause__ is None


def test_unicode_write_failure_is_controlled_without_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "secret" / "candidates.json"

    def fail_serialization(value: object) -> str:
        raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogate")

    monkeypatch.setattr(json_adapter, "canonical_json", fail_serialization)
    with pytest.raises(CandidateStorageError, match="write staging storage") as caught:
        JsonCandidateRepository(path).create(candidate("valid"))

    assert str(path) not in str(caught.value)
    assert "Unicode" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_failed_atomic_replace_preserves_previous_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    original = candidate("original")
    repository.create(original)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("interrupted")

    monkeypatch.setattr(json_adapter.os, "replace", fail_replace)
    with pytest.raises(CandidateStorageError):
        repository.create(candidate("new", chunk_index=1))

    assert JsonCandidateRepository(path).list() == (original,)
    assert list(tmp_path.glob(".candidates.json.*.tmp")) == []


def test_schema_v1_is_readable_and_successful_update_rewrites_v2(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("legacy"))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["schema_version"] = 1
    record = document["candidates"][0]
    for field in ("proposed_text", "revision", "review_history"):
        del record[field]
    path.write_text(json.dumps(document), encoding="utf-8")

    legacy = repository.get(original.candidate_id)
    assert (legacy.proposed_text, legacy.revision, legacy.review_history) == (None, 0, ())
    updated = mutated(legacy, proposed_metadata={"legacy": False})
    updated = replace(updated, proposed_text="reviewed text")
    repository.update(legacy.candidate_id, updated, expected_revision=0)

    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert rewritten["schema_version"] == 2
    assert repository.get(original.candidate_id) == updated


def test_genuine_schema_v1_all_states_round_trip_without_read_rewrite(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.json"
    legacy_items = [
        replace(candidate(f"legacy-{state.value}", chunk_index=index), state=state)
        for index, state in enumerate(CandidateState)
    ]
    before = write_schema_v1(path, legacy_items)

    loaded = JsonCandidateRepository(path).list()

    assert path.read_bytes() == before
    assert {item.state for item in loaded} == set(CandidateState)
    assert all(item.revision == 0 and item.review_history == () for item in loaded)
    assert all(
        item.proposed_metadata == {"legacy": ("kept", {"nested": True})}
        for item in loaded
    )
    assert all(item.provenance.run_metadata == {"legacy_run": (1, 2)} for item in loaded)
    assert all(
        item.provenance.transformations == ({"kind": "legacy-transform"},)
        for item in loaded
    )


def test_first_genuine_schema_v1_mutation_rewrites_every_record_deterministically(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    items = [candidate("legacy-b", chunk_index=1), candidate("legacy-a", chunk_index=0)]
    write_schema_v1(first_path, items)
    write_schema_v1(second_path, list(reversed(items)))

    for path in (first_path, second_path):
        repository = JsonCandidateRepository(path)
        target = repository.get(items[0].candidate_id)
        repository.update(
            target.candidate_id,
            mutated(target, proposed_metadata={"reviewed": True}),
            expected_revision=0,
        )

    first_document = json.loads(first_path.read_text(encoding="utf-8"))
    assert first_document["schema_version"] == 2
    assert all(
        set(record) == json_adapter.CANDIDATE_FIELDS_V2
        for record in first_document["candidates"]
    )
    assert first_path.read_bytes() == second_path.read_bytes()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("revision", True),
        ("revision", 1),
        ("proposed_text", "\ud800"),
        ("proposed_text", "   "),
    ],
)
def test_malformed_v2_candidate_lifecycle_fields_are_controlled(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "malformed-v2.json"
    repository = JsonCandidateRepository(path)
    repository.create(candidate("malformed lifecycle"))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["candidates"][0][field] = value
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MalformedStagingDataError):
        repository.list()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("revision", True),
        ("action", "approved"),
        ("previous_state", "unknown"),
        ("resulting_state", "unknown"),
        ("occurred_at", "2026-07-21T12:00:00"),
        ("occurred_at", 7),
        ("reason", ""),
        ("reason", "bad\ud800"),
    ],
)
def test_malformed_review_event_fields_are_controlled(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "malformed-event.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("event"))
    repository.update(original.candidate_id, mutated(original), expected_revision=0)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["candidates"][0]["review_history"][0][field] = value
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MalformedStagingDataError):
        repository.list()


def test_mixed_schema_record_and_unknown_review_event_field_are_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mixed.json"
    original = candidate("mixed")
    write_schema_v1(path, [original])
    document = json.loads(path.read_text(encoding="utf-8"))
    document["candidates"][0].update(
        {"proposed_text": None, "revision": 0, "review_history": []}
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(MalformedStagingDataError):
        JsonCandidateRepository(path).list()

    repository = JsonCandidateRepository(path)
    repository._write([mutated(original)])
    document = json.loads(path.read_text(encoding="utf-8"))
    document["candidates"][0]["review_history"][0]["unknown"] = None
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(MalformedStagingDataError):
        repository.list()


def test_stale_update_and_rewritten_history_leave_bytes_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("concurrent"))
    first = mutated(original)
    repository.update(original.candidate_id, first, expected_revision=0)
    before = path.read_bytes()

    with pytest.raises(CandidateRevisionConflictError):
        repository.update(original.candidate_id, first, expected_revision=0)
    assert path.read_bytes() == before

    rejected_event = CandidateReviewEvent(
        revision=2,
        action=CandidateReviewAction.REJECTED,
        occurred_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        previous_state=CandidateState.IN_REVIEW,
        resulting_state=CandidateState.REJECTED,
    )
    rewritten_first = replace(
        first.review_history[0], occurred_at=datetime(2026, 7, 22, tzinfo=timezone.utc)
    )
    rewritten = replace(
        first,
        state=CandidateState.REJECTED,
        revision=2,
        review_history=(rewritten_first, rejected_event),
    )
    with pytest.raises(CandidateRevisionConflictError):
        repository.update(original.candidate_id, rewritten, expected_revision=1)
    assert path.read_bytes() == before


def test_equal_instant_previous_event_timestamp_cannot_be_rewritten(
    tmp_path: Path,
) -> None:
    path = tmp_path / "event-offset-rewrite.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("event offset"))
    first = mutated(original)
    repository.update(original.candidate_id, first, expected_revision=0)
    before = path.read_bytes()

    rewritten_first = replace(
        first.review_history[0],
        occurred_at=first.review_history[0].occurred_at.astimezone(
            timezone(timedelta(hours=1))
        ),
    )
    rejected_event = CandidateReviewEvent(
        revision=2,
        action=CandidateReviewAction.REJECTED,
        occurred_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        previous_state=CandidateState.IN_REVIEW,
        resulting_state=CandidateState.REJECTED,
    )
    rewritten = replace(
        first,
        state=CandidateState.REJECTED,
        revision=2,
        review_history=(rewritten_first, rejected_event),
    )

    with pytest.raises(CandidateRevisionConflictError):
        repository.update(original.candidate_id, rewritten, expected_revision=1)
    assert path.read_bytes() == before


def test_equal_instant_provenance_timestamp_cannot_be_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "provenance-rewrite.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("provenance representation"))
    before = path.read_bytes()
    changed = replace(
        original.provenance,
        ingested_at=original.provenance.ingested_at.astimezone(
            timezone(timedelta(hours=1))
        ),
    )
    assert changed == original.provenance

    with pytest.raises(ImmutableCandidateFieldError):
        repository.update(
            original.candidate_id,
            mutated(original, provenance=changed),
            expected_revision=0,
        )
    assert path.read_bytes() == before


def test_equal_comparing_json_metadata_cannot_rewrite_provenance(tmp_path: Path) -> None:
    path = tmp_path / "provenance-metadata-rewrite.json"
    repository = JsonCandidateRepository(path)
    seeded = candidate("provenance metadata")
    original = repository.create(
        replace(
            seeded,
            provenance=replace(seeded.provenance, run_metadata={"batch": 1}),
        )
    )
    before = path.read_bytes()
    changed = replace(original.provenance, run_metadata={"batch": True})
    assert changed == original.provenance

    with pytest.raises(ImmutableCandidateFieldError):
        repository.update(
            original.candidate_id,
            mutated(original, provenance=changed),
            expected_revision=0,
        )
    assert path.read_bytes() == before


def test_missing_candidate_id_on_malformed_update_is_controlled(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing-update-id.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("missing update id"))
    malformed = mutated(original)
    object.__delattr__(malformed, "candidate_id")
    before = path.read_bytes()

    with pytest.raises(CandidateRevisionConflictError):
        repository.update(original.candidate_id, malformed, expected_revision=0)
    assert path.read_bytes() == before


def test_malformed_empty_appended_history_is_a_controlled_conflict(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("malformed update"))
    malformed = replace(original, proposed_metadata={"changed": True})
    object.__setattr__(malformed, "revision", 1)
    before = path.read_bytes()

    with pytest.raises(CandidateRevisionConflictError):
        repository.update(original.candidate_id, malformed, expected_revision=0)

    assert path.read_bytes() == before


def test_malformed_appended_event_is_a_controlled_conflict_without_writing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "malformed-event-update.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("malformed event update"))
    malformed = replace(original, proposed_metadata={"changed": True})
    object.__setattr__(malformed, "revision", 1)
    object.__setattr__(malformed, "review_history", (object(),))
    before = path.read_bytes()

    with pytest.raises(CandidateRevisionConflictError):
        repository.update(original.candidate_id, malformed, expected_revision=0)

    assert path.read_bytes() == before


def test_all_rejected_update_shapes_preserve_storage_bytes(tmp_path: Path) -> None:
    path = tmp_path / "rejected-updates.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("immutable"))
    first = mutated(original)
    before = path.read_bytes()

    wrong_id = replace(first)
    object.__setattr__(wrong_id, "candidate_id", "sha256:wrong")
    two_events = (
        CandidateReviewEvent(
            1,
            CandidateReviewAction.REVISED,
            datetime(2026, 7, 20, tzinfo=timezone.utc),
            CandidateState.STAGED,
            CandidateState.STAGED,
        ),
        CandidateReviewEvent(
            2,
            CandidateReviewAction.ACCEPTED,
            datetime(2026, 7, 21, tzinfo=timezone.utc),
            CandidateState.STAGED,
            CandidateState.IN_REVIEW,
        ),
    )
    appended_twice = replace(
        original,
        state=CandidateState.IN_REVIEW,
        revision=2,
        review_history=two_events,
    )
    attempts: list[tuple[str, LessonCandidate, int, type[Exception]]] = [
        (original.candidate_id, first, 1, CandidateRevisionConflictError),
        (original.candidate_id, original, 0, CandidateRevisionConflictError),
        (original.candidate_id, appended_twice, 0, CandidateRevisionConflictError),
        (original.candidate_id, wrong_id, 0, ImmutableCandidateFieldError),
        (
            original.candidate_id,
            mutated(original, text="changed source text"),
            0,
            ImmutableCandidateFieldError,
        ),
        (
            original.candidate_id,
            mutated(
                original,
                provenance=replace(original.provenance, source_fingerprint="changed"),
            ),
            0,
            ImmutableCandidateFieldError,
        ),
        ("sha256:missing", first, 0, CandidateNotFoundError),
    ]

    for candidate_id, proposed, expected, error_type in attempts:
        with pytest.raises(error_type):
            repository.update(
                candidate_id, proposed, expected_revision=expected
            )
        assert path.read_bytes() == before


@pytest.mark.parametrize("expected_revision", [True, -1, 1.5, "0"])
def test_invalid_expected_revision_never_writes(
    tmp_path: Path, expected_revision: object
) -> None:
    path = tmp_path / "invalid-expected.json"
    repository = JsonCandidateRepository(path)
    original = repository.create(candidate("expected"))
    before = path.read_bytes()

    with pytest.raises(ValueError, match="expected revision"):
        repository.update(
            original.candidate_id,
            mutated(original),
            expected_revision=expected_revision,  # type: ignore[arg-type]
        )

    assert path.read_bytes() == before


def test_staging_never_touches_vault_projection_exports_or_ml_datasets(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    approved = vault / "approved.md"
    projection = tmp_path / "lessons.jsonl"
    export = tmp_path / "export.jsonl"
    ml_dataset = tmp_path / "training.csv"
    protected = {
        approved: b"---\nid: approved\n---\ncanonical\n",
        projection: b'{"id":"approved"}\n',
        export: b'{"id":"exported"}\n',
        ml_dataset: b"text,topic\ncanonical,testing\n",
    }
    for path, contents in protected.items():
        path.write_bytes(contents)

    staging_path = tmp_path / "staging" / "candidates.json"
    repository = JsonCandidateRepository(staging_path)
    staged = repository.create(candidate("isolated"))
    repository.get(staged.candidate_id)
    repository.list()
    repository.update(
        staged.candidate_id,
        mutated(staged, state=CandidateState.REJECTED),
        expected_revision=0,
    )

    assert {path: path.read_bytes() for path in protected} == protected
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == [
        "export.jsonl",
        "lessons.jsonl",
        "staging",
        "staging/candidates.json",
        "training.csv",
        "vault",
        "vault/approved.md",
    ]
