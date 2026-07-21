"""Deterministic filesystem adapter for lesson-candidate staging."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Mapping, Sequence

from lele_manager.application.lesson_candidate import (
    CandidateNotFoundError,
    CandidateProvenance,
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
from lele_manager.core.json_compat import canonical_json

SCHEMA_VERSION = 2
ROOT_FIELDS = {"candidates", "schema_version"}
CANDIDATE_FIELDS_V1 = {
    "candidate_id", "proposed_metadata", "provenance", "state", "text",
}
CANDIDATE_FIELDS_V2 = CANDIDATE_FIELDS_V1 | {
    "proposed_text", "revision", "review_history",
}
REVIEW_EVENT_FIELDS = {
    "action", "occurred_at", "previous_state", "reason", "resulting_state", "revision",
}
PROVENANCE_FIELDS = {
    "chunk_index", "ingested_at", "run_metadata", "source_fingerprint",
    "source_kind", "source_logical_name", "source_span", "transformations",
}
SOURCE_SPAN_FIELDS = {"end", "start"}


def _json_value(value: object) -> object:
    """Thaw immutable domain JSON values into serializer-native containers."""
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _candidate_to_dict(candidate: LessonCandidate) -> dict[str, object]:
    provenance = candidate.provenance
    span = provenance.source_span
    return {
        "candidate_id": candidate.candidate_id,
        "proposed_text": candidate.proposed_text,
        "proposed_metadata": _json_value(candidate.proposed_metadata),
        "provenance": {
            "chunk_index": provenance.chunk_index,
            "ingested_at": provenance.ingested_at.isoformat(),
            "run_metadata": _json_value(provenance.run_metadata),
            "source_fingerprint": provenance.source_fingerprint,
            "source_kind": provenance.source_kind.value,
            "source_logical_name": provenance.source_logical_name,
            "source_span": None if span is None else {"end": span.end, "start": span.start},
            "transformations": _json_value(provenance.transformations),
        },
        "state": candidate.state.value,
        "revision": candidate.revision,
        "review_history": [
            {
                "action": event.action.value,
                "occurred_at": event.occurred_at.isoformat(),
                "previous_state": event.previous_state.value,
                "reason": event.reason,
                "resulting_state": event.resulting_state.value,
                "revision": event.revision,
            }
            for event in candidate.review_history
        ],
        "text": candidate.text,
    }


def _object(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise MalformedStagingDataError(f"{name} must be an object")
    return value


def _exact_fields(value: Mapping[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise MalformedStagingDataError(f"{name} has missing or unknown fields")


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _candidate_from_dict(
    value: object, position: int, schema_version: int
) -> LessonCandidate:
    try:
        record = _object(value, f"candidate {position}")
        expected_fields = (
            CANDIDATE_FIELDS_V1 if schema_version == 1 else CANDIDATE_FIELDS_V2
        )
        _exact_fields(record, expected_fields, f"candidate {position}")
        provenance_data = _object(record["provenance"], f"candidate {position} provenance")
        _exact_fields(provenance_data, PROVENANCE_FIELDS, f"candidate {position} provenance")
        raw_span = provenance_data["source_span"]
        span_data = None if raw_span is None else _object(raw_span, "source span")
        if span_data is not None:
            _exact_fields(span_data, SOURCE_SPAN_FIELDS, "source span")
        span = (
            None
            if span_data is None
            else SourceSpan(start=span_data["start"], end=span_data["end"])  # type: ignore[arg-type]
        )
        raw_transformations = provenance_data["transformations"]
        if not isinstance(raw_transformations, list):
            raise MalformedStagingDataError("transformations must be an array")
        transformations = tuple(
            _object(item, "transformation metadata") for item in raw_transformations
        )
        run_metadata = _object(provenance_data["run_metadata"], "run metadata")
        proposed_raw = record["proposed_metadata"]
        proposed = None if proposed_raw is None else _object(proposed_raw, "proposed metadata")
        review_history: tuple[CandidateReviewEvent, ...] = ()
        if schema_version == 2:
            raw_history = record["review_history"]
            if not isinstance(raw_history, list):
                raise MalformedStagingDataError("review history must be an array")
            events: list[CandidateReviewEvent] = []
            for event_position, raw_event in enumerate(raw_history, start=1):
                event = _object(raw_event, f"review event {event_position}")
                _exact_fields(event, REVIEW_EVENT_FIELDS, f"review event {event_position}")
                events.append(
                    CandidateReviewEvent(
                        revision=event["revision"],  # type: ignore[arg-type]
                        action=CandidateReviewAction(event["action"]),
                        occurred_at=datetime.fromisoformat(event["occurred_at"]),  # type: ignore[arg-type]
                        previous_state=CandidateState(event["previous_state"]),
                        resulting_state=CandidateState(event["resulting_state"]),
                        reason=event["reason"],  # type: ignore[arg-type]
                    )
                )
            review_history = tuple(events)
        provenance = CandidateProvenance(
            source_kind=SourceKind(provenance_data["source_kind"]),
            source_logical_name=provenance_data["source_logical_name"],  # type: ignore[arg-type]
            source_fingerprint=provenance_data["source_fingerprint"],  # type: ignore[arg-type]
            ingested_at=datetime.fromisoformat(provenance_data["ingested_at"]),  # type: ignore[arg-type]
            chunk_index=provenance_data["chunk_index"],  # type: ignore[arg-type]
            source_span=span,
            run_metadata=run_metadata,
            transformations=transformations,
        )
        candidate = LessonCandidate(
            text=record["text"],  # type: ignore[arg-type]
            provenance=provenance,
            proposed_text=record["proposed_text"] if schema_version == 2 else None,  # type: ignore[arg-type]
            proposed_metadata=proposed,
            state=CandidateState(record["state"]),
            revision=record["revision"] if schema_version == 2 else 0,  # type: ignore[arg-type]
            review_history=review_history,
        )
        stored_id = record["candidate_id"]
        if not isinstance(stored_id, str) or stored_id != candidate.candidate_id:
            raise MalformedStagingDataError(f"candidate {position} has an invalid ID")
        return candidate
    except MalformedStagingDataError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise MalformedStagingDataError(f"candidate {position} is malformed") from exc


class JsonCandidateRepository:
    """One versioned JSON document, atomically replaced and sorted by ID."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def _load(self) -> list[LessonCandidate]:
        try:
            if not self._path.exists():
                return []
            raw = self._path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise MalformedStagingDataError("staging data is not valid UTF-8") from exc
        except OSError:
            raise CandidateStorageError("could not read staging storage") from None
        try:
            document = json.loads(
                raw, parse_constant=_reject_constant, object_pairs_hook=_unique_object
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise MalformedStagingDataError("staging data is not valid JSON") from exc
        root = _object(document, "staging data")
        _exact_fields(root, ROOT_FIELDS, "staging data")
        schema_version = root["schema_version"]
        if type(schema_version) is not int or schema_version not in (1, SCHEMA_VERSION):
            raise MalformedStagingDataError("unsupported staging schema version")
        records = root["candidates"]
        if not isinstance(records, list):
            raise MalformedStagingDataError("staging candidates must be an array")
        candidates: list[LessonCandidate] = []
        seen: set[str] = set()
        for position, record in enumerate(records, start=1):
            candidate = _candidate_from_dict(record, position, schema_version)
            if candidate.candidate_id in seen:
                raise DuplicateCandidateIdError(
                    f"duplicate candidate id {candidate.candidate_id!r}"
                )
            seen.add(candidate.candidate_id)
            candidates.append(candidate)
        return sorted(candidates, key=lambda item: item.candidate_id)

    def _write(self, candidates: Sequence[LessonCandidate]) -> None:
        document = {
            "candidates": [_candidate_to_dict(item) for item in sorted(
                candidates, key=lambda candidate: candidate.candidate_id
            )],
            "schema_version": SCHEMA_VERSION,
        }
        temporary_path: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as target:
                temporary_path = Path(target.name)
                target.write(canonical_json(document) + "\n")
                target.flush()
                os.fsync(target.fileno())
            if self._path.exists():
                os.chmod(temporary_path, stat.S_IMODE(self._path.stat().st_mode))
            os.replace(temporary_path, self._path)
            temporary_path = None
        except (OSError, UnicodeError):
            raise CandidateStorageError("could not write staging storage") from None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def create(self, candidate: LessonCandidate) -> LessonCandidate:
        candidates = self._load()
        if any(item.candidate_id == candidate.candidate_id for item in candidates):
            raise DuplicateCandidateIdError(
                f"duplicate candidate id {candidate.candidate_id!r}"
            )
        self._write((*candidates, candidate))
        return candidate

    def get(self, candidate_id: str) -> LessonCandidate:
        for candidate in self._load():
            if candidate.candidate_id == candidate_id:
                return candidate
        raise CandidateNotFoundError(f"candidate {candidate_id!r} was not found")

    def list(self) -> tuple[LessonCandidate, ...]:
        return tuple(self._load())

    def update(
        self,
        candidate_id: str,
        candidate: LessonCandidate,
        *,
        expected_revision: int,
    ) -> LessonCandidate:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected revision must be a non-negative integer")
        candidates = self._load()
        for position, existing in enumerate(candidates):
            if existing.candidate_id != candidate_id:
                continue
            if existing.revision != expected_revision:
                raise CandidateRevisionConflictError("candidate revision conflict")
            if type(candidate) is not LessonCandidate:
                raise CandidateRevisionConflictError("candidate update is malformed")
            try:
                proposed_id = candidate.candidate_id
            except AttributeError:
                raise CandidateRevisionConflictError(
                    "candidate update is malformed"
                ) from None
            if proposed_id != candidate_id:
                raise ImmutableCandidateFieldError(
                    "candidate text, identity and provenance are immutable"
                )
            try:
                candidate_data = _candidate_to_dict(candidate)
                validated_candidate = _candidate_from_dict(
                    candidate_data, position + 1, SCHEMA_VERSION
                )
            except (
                MalformedStagingDataError,
                AttributeError,
                IndexError,
                KeyError,
                TypeError,
                ValueError,
            ):
                raise CandidateRevisionConflictError(
                    "candidate update is malformed"
                ) from None
            existing_data = _candidate_to_dict(existing)
            if existing.text != validated_candidate.text or canonical_json(
                existing_data["provenance"]
            ) != canonical_json(candidate_data["provenance"]):
                raise ImmutableCandidateFieldError(
                    "candidate text, identity and provenance are immutable"
                )
            if validated_candidate.revision != expected_revision + 1:
                raise CandidateRevisionConflictError("candidate revision must increment once")
            candidate_history_data = candidate_data["review_history"]
            existing_history_data = existing_data["review_history"]
            assert isinstance(candidate_history_data, list)
            assert isinstance(existing_history_data, list)
            if (
                len(validated_candidate.review_history) != len(existing.review_history) + 1
                or canonical_json(candidate_history_data[:-1])
                != canonical_json(existing_history_data)
            ):
                raise CandidateRevisionConflictError("candidate review history must append once")
            candidates[position] = validated_candidate
            self._write(candidates)
            return validated_candidate
        raise CandidateNotFoundError(f"candidate {candidate_id!r} was not found")
