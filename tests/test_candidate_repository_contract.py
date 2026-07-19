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

    updated = replace(
        original,
        state=CandidateState.IN_REVIEW,
        proposed_metadata={"topic": "revised"},
    )
    assert repository.update(original.candidate_id, updated) == updated
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
        repository.update(original.candidate_id, replace(original, provenance=later_provenance))
    with pytest.raises(ImmutableCandidateFieldError, match="immutable"):
        repository.update(original.candidate_id, replace(original, text="different"))
    changed_source = replace(original.provenance, source_logical_name="elsewhere.md")
    with pytest.raises(ImmutableCandidateFieldError, match="immutable"):
        repository.update(original.candidate_id, replace(original, provenance=changed_source))
    with pytest.raises(CandidateNotFoundError):
        repository.update("sha256:genuinely-missing", original)


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
        '{"schema_version":2,"candidates":[]}',
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
    repository.update(staged.candidate_id, replace(staged, state=CandidateState.REJECTED))

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
