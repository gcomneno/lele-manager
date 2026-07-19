from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo

import pytest

from lele_manager.application.lesson_candidate import (
    CandidateProvenance,
    CandidateState,
    LessonCandidate,
    SourceSpan,
)
from lele_manager.application.raw_source import SourceKind


def provenance(**changes: object) -> CandidateProvenance:
    values: dict[str, object] = {
        "source_kind": SourceKind.PLAIN_TEXT,
        "source_logical_name": "notes.txt",
        "source_fingerprint": "sha256:source",
        "ingested_at": datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc),
        "chunk_index": 2,
        "source_span": SourceSpan(10, 24),
        "run_metadata": {"run": "import-7"},
        "transformations": ({"kind": "trim", "version": 1},),
    }
    values.update(changes)
    return CandidateProvenance(**values)  # type: ignore[arg-type]


class NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt: datetime | None) -> None:
        return None

    def dst(self, dt: datetime | None) -> timedelta | None:
        return None


def test_candidate_preserves_reviewable_content_and_complete_provenance() -> None:
    candidate = LessonCandidate(
        "candidate text",
        provenance(),
        proposed_metadata={"topic": "testing", "tags": ["pytest"]},
    )

    assert candidate.text == "candidate text"
    assert candidate.proposed_metadata == {"topic": "testing", "tags": ("pytest",)}
    assert candidate.provenance.chunk_index == 2
    assert candidate.provenance.source_span == SourceSpan(10, 24)
    assert candidate.provenance.run_metadata == {"run": "import-7"}
    assert candidate.provenance.transformations == ({"kind": "trim", "version": 1},)
    assert candidate.state is CandidateState.STAGED


def test_metadata_is_deeply_copied_and_immutable() -> None:
    run_metadata = {"environment": {"labels": ["local"]}}
    transformation = {"details": {"steps": ["trim"]}}
    proposed_metadata = {"classification": {"tags": ["testing"]}}
    candidate = LessonCandidate(
        "text",
        provenance(run_metadata=run_metadata, transformations=(transformation,)),
        proposed_metadata=proposed_metadata,
    )

    run_metadata["environment"]["labels"].append("mutated")  # type: ignore[index,union-attr]
    transformation["details"]["steps"].append("mutated")  # type: ignore[index,union-attr]
    proposed_metadata["classification"]["tags"].append("mutated")  # type: ignore[index,union-attr]

    assert candidate.provenance.run_metadata == {
        "environment": {"labels": ("local",)}
    }
    assert candidate.provenance.transformations == (
        {"details": {"steps": ("trim",)}},
    )
    assert candidate.proposed_metadata == {
        "classification": {"tags": ("testing",)}
    }

    with pytest.raises(TypeError):
        candidate.provenance.run_metadata["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.provenance.transformations[0]["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.proposed_metadata["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.provenance.run_metadata["environment"]["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.provenance.transformations[0]["details"]["steps"][0] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.proposed_metadata["classification"]["tags"][0] = "x"  # type: ignore[index]


def test_identity_is_stable_for_normalized_input_and_excludes_timestamp_metadata() -> None:
    first = LessonCandidate("one\r\ntwo", provenance())
    replayed = LessonCandidate(
        "one\ntwo",
        provenance(
            ingested_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
            run_metadata={"different": True},
            transformations=({"kind": "enrichment", "model": "none"},),
        ),
        proposed_metadata={"topic": "changed"},
        state=CandidateState.IN_REVIEW,
    )

    assert first.candidate_id == replayed.candidate_id
    assert first.candidate_id == (
        "sha256:510995b11a560f11055f41ef5805ec8dda8a5d63e33920bd0b0eb0284ebe8e39"
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"text": "different"},
        {"provenance": provenance(source_logical_name="other.txt")},
        {"provenance": provenance(source_fingerprint="sha256:other")},
        {"provenance": provenance(chunk_index=3)},
        {"provenance": provenance(source_span=SourceSpan(11, 24))},
    ],
)
def test_identity_changes_for_distinct_text_or_source_chunk_identity(
    changed: dict[str, object],
) -> None:
    baseline = LessonCandidate("text", provenance())
    values: dict[str, object] = {"text": "text", "provenance": provenance()}
    values.update(changed)

    candidate = LessonCandidate(**values)  # type: ignore[arg-type]

    assert candidate.candidate_id != baseline.candidate_id


def test_lifecycle_states_are_explicit_without_premature_transition_policy() -> None:
    candidate = LessonCandidate("text", provenance())

    assert [state.value for state in CandidateState] == [
        "staged",
        "in_review",
        "rejected",
        "approved",
    ]
    assert replace(candidate, state=CandidateState.REJECTED).state is CandidateState.REJECTED


def test_invalid_provenance_and_metadata_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        provenance(ingested_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="JSON-compatible"):
        LessonCandidate("text", provenance(), proposed_metadata={"bad": object()})
    with pytest.raises(ValueError, match="chunk index"):
        provenance(chunk_index=-1)
    with pytest.raises(ValueError, match="source span"):
        SourceSpan(4, 3)


def test_timezone_with_no_utc_offset_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        provenance(ingested_at=datetime(2026, 1, 1, tzinfo=NoOffsetTimezone()))


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf"), object()])
def test_non_json_metadata_leaves_are_rejected(invalid: object) -> None:
    with pytest.raises(ValueError, match="JSON-compatible"):
        LessonCandidate("text", provenance(), proposed_metadata={"bad": invalid})


def test_non_string_metadata_keys_and_cycles_are_rejected() -> None:
    cyclic_mapping: dict[str, object] = {}
    cyclic_mapping["self"] = cyclic_mapping
    cyclic_list: list[object] = []
    cyclic_list.append(cyclic_list)
    tuple_cycle_list: list[object] = []
    cyclic_tuple = (tuple_cycle_list,)
    tuple_cycle_list.append(cyclic_tuple)

    invalid_values: list[object] = [
        {1: "value"},
        cyclic_mapping,
        {"items": cyclic_list},
        {"items": cyclic_tuple},
    ]
    for invalid in invalid_values:
        with pytest.raises(ValueError, match="JSON-compatible"):
            LessonCandidate("text", provenance(), proposed_metadata=invalid)  # type: ignore[arg-type]


def test_repeated_non_cyclic_metadata_references_are_allowed_and_copied() -> None:
    shared = ["value"]
    candidate = LessonCandidate(
        "text", provenance(), proposed_metadata={"first": shared, "second": shared}
    )

    shared.append("changed")
    assert candidate.proposed_metadata == {"first": ("value",), "second": ("value",)}


def test_surrogate_in_candidate_text_is_rejected() -> None:
    with pytest.raises(ValueError, match="candidate text.*surrogate"):
        LessonCandidate("invalid \ud800 text", provenance())


@pytest.mark.parametrize("field", ["source_logical_name", "source_fingerprint"])
def test_surrogate_in_source_identity_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match=f"{field.replace('_', ' ')}.*surrogate"):
        provenance(**{field: "invalid\udfff"})


def test_surrogate_in_metadata_keys_and_nested_values_is_rejected() -> None:
    with pytest.raises(ValueError, match="key.*surrogate"):
        LessonCandidate("text", provenance(), proposed_metadata={"bad\ud800": "value"})
    with pytest.raises(ValueError, match="surrogate"):
        provenance(run_metadata={"nested": [{"value": "bad\udfff"}]})
    with pytest.raises(ValueError, match="surrogate"):
        provenance(transformations=({"nested": ["bad\ud800"]},))


def test_valid_unicode_is_accepted_without_changing_identity_semantics() -> None:
    candidate = LessonCandidate(
        "Lezione caffè 😀 \U00020000",
        provenance(
            source_logical_name="appunti-è-😀.md",
            source_fingerprint="impronta-\U00020000",
            run_metadata={"città": {"simbolo": "😀"}},
        ),
        proposed_metadata={"descrizione": "caffè \U00020000"},
    )

    assert candidate.text == "Lezione caffè 😀 \U00020000"
    assert candidate.proposed_metadata == {"descrizione": "caffè \U00020000"}
