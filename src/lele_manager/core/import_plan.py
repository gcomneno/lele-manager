from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class LessonChangeKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    REMOVED = "removed"


class DuplicatePolicy(str, Enum):
    ERROR = "error"
    SKIP = "skip"
    OVERWRITE = "overwrite"


class DuplicateResolution(str, Enum):
    BLOCKED = "blocked"
    KEPT_FIRST = "kept_first"
    KEPT_LAST = "kept_last"


@dataclass(frozen=True)
class LessonChange:
    lesson_id: str
    kind: LessonChangeKind
    path: str | None = None


@dataclass(frozen=True)
class DuplicateId:
    lesson_id: str
    first_path: str
    duplicate_path: str
    policy: DuplicatePolicy
    resolution: DuplicateResolution


@dataclass(frozen=True)
class ValidationProblem:
    code: str
    message: str
    path: str | None = None
    field: str | None = None
    blocking: bool = False


@dataclass(frozen=True)
class IgnoredFile:
    path: str
    reason: str


@dataclass(frozen=True)
class PendingSourceWrite:
    path: str
    reason: str


@dataclass
class ImportPlan:
    changes: list[LessonChange] = field(default_factory=list)
    duplicates: list[DuplicateId] = field(default_factory=list)
    validation_problems: list[ValidationProblem] = field(default_factory=list)
    ignored_files: list[IgnoredFile] = field(default_factory=list)
    pending_source_writes: list[PendingSourceWrite] = field(default_factory=list)
    replace_all: bool = False
    candidate_records: dict[str, Mapping[str, Any]] = field(
        default_factory=dict, repr=False
    )
    pending_source_contents: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def blocking(self) -> bool:
        return any(problem.blocking for problem in self.validation_problems)

    def to_dict(self, *, include_candidate_records: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "changes": [
                {"id": item.lesson_id, "kind": item.kind.value, "path": item.path}
                for item in sorted(
                    self.changes,
                    key=lambda item: (item.lesson_id, item.kind.value, item.path or ""),
                )
            ],
            "duplicates": [
                {
                    "id": item.lesson_id,
                    "first_path": item.first_path,
                    "duplicate_path": item.duplicate_path,
                    "policy": item.policy.value,
                    "resolution": item.resolution.value,
                }
                for item in sorted(
                    self.duplicates,
                    key=lambda item: (
                        item.lesson_id,
                        item.first_path,
                        item.duplicate_path,
                    ),
                )
            ],
            "validation_problems": [
                {
                    "code": item.code,
                    "message": item.message,
                    "path": item.path,
                    "field": item.field,
                    "blocking": item.blocking,
                }
                for item in sorted(
                    self.validation_problems,
                    key=lambda item: (
                        item.path or "",
                        item.code,
                        item.field or "",
                        item.message,
                    ),
                )
            ],
            "ignored_files": [
                {"path": item.path, "reason": item.reason}
                for item in sorted(
                    self.ignored_files, key=lambda item: (item.path, item.reason)
                )
            ],
            "pending_source_writes": [
                {"path": item.path, "reason": item.reason}
                for item in sorted(
                    self.pending_source_writes,
                    key=lambda item: (item.path, item.reason),
                )
            ],
            "replace_all": self.replace_all,
            "blocking": self.blocking,
        }
        if include_candidate_records:
            result["candidate_records"] = [
                _json_native(self.candidate_records[lesson_id])
                for lesson_id in sorted(self.candidate_records)
            ]
        return result


def _json_native(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {
            str(key): _json_native(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_native(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_json_native(item) for item in value), key=repr)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Value is not JSON-native: {type(value).__name__}")
