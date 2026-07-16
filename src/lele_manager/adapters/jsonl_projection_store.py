"""JSONL compatibility adapter for the projection-store port."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import stat
from typing import Any

from lele_manager.core.json_compat import canonical_json
from lele_manager.core.projection_store import (
    DuplicateLessonIdError,
    LessonOrder,
    LessonQuery,
    LessonRecord,
    MalformedProjectionError,
    ProjectionStatistics,
)


def _canonical_json(record: LessonRecord) -> str:
    try:
        return canonical_json(record)
    except (TypeError, ValueError) as exc:
        raise MalformedProjectionError(f"lesson record is not JSON serializable: {exc}") from exc


def _generation(records: Sequence[LessonRecord]) -> str:
    digest = hashlib.sha256()
    # SNAPSHOT order is observable, so it is part of the generation.
    for record in records:
        digest.update(_canonical_json(record).encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def _record_id(record: LessonRecord, position: int) -> str:
    if "id" not in record or record["id"] is None:
        raise MalformedProjectionError(f"record {position} has no id")
    lesson_id = str(record["id"])
    if not lesson_id:
        raise MalformedProjectionError(f"record {position} has an empty id")
    return lesson_id


def _as_optional_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _created_at(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp()
    except (ValueError, OSError):
        return None


def _importance_sort_value(record: LessonRecord) -> float:
    value = _as_optional_number(record.get("importance"))
    return value if value is not None else float("-inf")


@dataclass(frozen=True)
class JsonlProjectionSnapshot:
    _records: tuple[dict[str, Any], ...]
    _by_id: dict[str, dict[str, Any]]
    generation: str
    statistics: ProjectionStatistics

    def get(self, lesson_id: str) -> LessonRecord | None:
        record = self._by_id.get(lesson_id)
        return deepcopy(record) if record is not None else None

    def list(self, query: LessonQuery = LessonQuery()) -> tuple[LessonRecord, ...]:
        topics = set(query.topics) if query.topics is not None else None
        sources = set(query.sources) if query.sources is not None else None
        required_tags = set(query.tags) if query.tags is not None else None
        needle = query.text.casefold() if query.text else None
        matches: list[dict[str, Any]] = []
        for record in self._records:
            if needle and needle not in str(record.get("text") or "").casefold():
                continue
            if topics is not None and str(record.get("topic") or "") not in topics:
                continue
            if sources is not None and str(record.get("source") or "") not in sources:
                continue
            raw_tags = record.get("tags")
            record_tags = {str(tag) for tag in raw_tags} if isinstance(raw_tags, list) else set()
            if required_tags is not None and not required_tags.issubset(record_tags):
                continue
            importance = _as_optional_number(record.get("importance"))
            if query.importance_gte is not None and (
                importance is None or importance < query.importance_gte
            ):
                continue
            if query.importance_lte is not None and (
                importance is None or importance > query.importance_lte
            ):
                continue
            matches.append(record)

        if query.order is LessonOrder.ID:
            matches.sort(key=lambda row: str(row["id"]))
        elif query.order is LessonOrder.CREATED_AT_DESC:
            matches.sort(key=lambda row: str(row["id"]))
            matches.sort(
                key=lambda row: _created_at(row.get("created_at")) or float("-inf"),
                reverse=True,
            )
        elif query.order is LessonOrder.RELEVANCE:
            matches.sort(key=lambda row: str(row["id"]))
            matches.sort(
                key=lambda row: _created_at(row.get("created_at")) or float("-inf"),
                reverse=True,
            )
            matches.sort(
                key=_importance_sort_value,
                reverse=True,
            )
        if query.limit is not None:
            matches = matches[: query.limit]
        return tuple(deepcopy(record) for record in matches)


def _make_snapshot(records: Sequence[LessonRecord]) -> JsonlProjectionSnapshot:
    copied: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    topics: set[str] = set()
    tags: set[str] = set()
    for position, raw_record in enumerate(records, start=1):
        if not isinstance(raw_record, Mapping):
            raise MalformedProjectionError(f"record {position} is not an object")
        record = deepcopy(dict(raw_record))
        lesson_id = _record_id(record, position)
        if lesson_id in by_id:
            raise DuplicateLessonIdError(f"duplicate lesson id {lesson_id!r}")
        # Validate serializability before any publication can begin.
        _canonical_json(record)
        copied.append(record)
        by_id[lesson_id] = record
        topic = record.get("topic")
        if topic is not None and str(topic):
            topics.add(str(topic))
        raw_tags = record.get("tags")
        if isinstance(raw_tags, list):
            tags.update(str(tag) for tag in raw_tags if str(tag))
    immutable_records = tuple(copied)
    return JsonlProjectionSnapshot(
        _records=immutable_records,
        _by_id=by_id,
        generation=_generation(immutable_records),
        statistics=ProjectionStatistics(len(copied), len(topics), len(tags)),
    )


class JsonlProjectionStore:
    """A UTF-8 JSONL projection with atomic whole-snapshot publication."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def snapshot(self) -> JsonlProjectionSnapshot:
        if not self._path.exists():
            return _make_snapshot(())
        records: list[LessonRecord] = []
        try:
            with self._path.open("r", encoding="utf-8") as source:
                for line_number, line in enumerate(source, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise MalformedProjectionError(
                            f"malformed JSONL record at line {line_number}: {exc.msg}"
                        ) from exc
                    if not isinstance(record, dict):
                        raise MalformedProjectionError(
                            f"JSONL record at line {line_number} is not an object"
                        )
                    records.append(record)
        except UnicodeDecodeError as exc:
            raise MalformedProjectionError(f"projection is not valid UTF-8: {exc}") from exc
        return _make_snapshot(records)

    def publish(self, records: Sequence[LessonRecord]) -> JsonlProjectionSnapshot:
        # ID ordering makes both bytes and generation independent of input order.
        snapshot = _make_snapshot(records)
        ordered = sorted(snapshot.list(), key=lambda row: str(row["id"]))
        snapshot = _make_snapshot(ordered)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self._path.parent, prefix=f".{self._path.name}.",
                suffix=".tmp", delete=False
            ) as target:
                temporary_path = Path(target.name)
                for record in snapshot.list():
                    target.write(_canonical_json(record) + "\n")
                target.flush()
                os.fsync(target.fileno())
            if self._path.exists():
                os.chmod(temporary_path, stat.S_IMODE(self._path.stat().st_mode))
            os.replace(temporary_path, self._path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return snapshot


class JsonlLegacyAppendFacade:
    """JSONL-only compatibility API, deliberately outside ProjectionStore."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, record: LessonRecord) -> None:
        incoming = _make_snapshot((record,)).list()[0]
        existing = JsonlProjectionStore(self._path).snapshot()
        lesson_id = str(incoming["id"])
        if existing.get(lesson_id) is not None:
            raise DuplicateLessonIdError(f"duplicate lesson id {lesson_id!r}")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        needs_separator = self._path.exists() and self._path.stat().st_size > 0
        if needs_separator:
            with self._path.open("rb") as source:
                source.seek(-1, os.SEEK_END)
                needs_separator = source.read(1) not in (b"\n", b"\r")
        with self._path.open("a", encoding="utf-8") as target:
            if needs_separator:
                target.write("\n")
            target.write(json.dumps(incoming, ensure_ascii=False, default=str) + "\n")
