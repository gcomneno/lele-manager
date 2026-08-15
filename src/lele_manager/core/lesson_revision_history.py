"""Durable per-Vault editorial history for canonical LeLe revisions."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Literal


SCHEMA_VERSION = 1
MAX_HISTORY_BYTES = 256 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024

_LOCK = RLock()

RevisionAction = Literal["baseline", "edit", "rollback"]


class LessonRevisionHistoryError(Exception):
    """Revision history cannot be safely read or written."""


class LessonRevisionHistoryConflictError(LessonRevisionHistoryError):
    """The requested append does not extend the current history."""


@dataclass(frozen=True)
class LessonRevision:
    lesson_id: str
    revision: int
    canonical_fingerprint: str
    occurred_at: str
    action: RevisionAction
    relative_path: str
    markdown: str
    reason: str | None = None
    rollback_from_revision: int | None = None


def canonical_fingerprint(markdown: bytes) -> str:
    return f"sha256:{hashlib.sha256(markdown).hexdigest()}"


def _empty_document() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "lessons": {}}


def _revision_from_dict(lesson_id: str, raw: object) -> LessonRevision:
    if not isinstance(raw, dict):
        raise LessonRevisionHistoryError("lesson revision history is malformed")

    revision = raw.get("revision")
    fingerprint = raw.get("canonical_fingerprint")
    occurred_at = raw.get("occurred_at")
    action = raw.get("action")
    relative_path = raw.get("relative_path")
    markdown = raw.get("markdown")
    reason = raw.get("reason")
    rollback_from = raw.get("rollback_from_revision")

    if type(revision) is not int or revision < 0:
        raise LessonRevisionHistoryError("lesson revision number is malformed")
    if (
        not isinstance(fingerprint, str)
        or not fingerprint.startswith("sha256:")
        or len(fingerprint) != 71
    ):
        raise LessonRevisionHistoryError("lesson revision fingerprint is malformed")
    if not isinstance(occurred_at, str) or not occurred_at:
        raise LessonRevisionHistoryError("lesson revision timestamp is malformed")
    if action not in ("baseline", "edit", "rollback"):
        raise LessonRevisionHistoryError("lesson revision action is malformed")
    if not isinstance(relative_path, str) or not relative_path:
        raise LessonRevisionHistoryError("lesson revision path is malformed")
    if not isinstance(markdown, str):
        raise LessonRevisionHistoryError("lesson revision snapshot is malformed")
    encoded = markdown.encode("utf-8")
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise LessonRevisionHistoryError("lesson revision snapshot exceeds size limits")
    if canonical_fingerprint(encoded) != fingerprint:
        raise LessonRevisionHistoryError("lesson revision fingerprint does not match snapshot")
    if reason is not None and not isinstance(reason, str):
        raise LessonRevisionHistoryError("lesson revision reason is malformed")
    if rollback_from is not None and (type(rollback_from) is not int or rollback_from < 0):
        raise LessonRevisionHistoryError("lesson rollback source revision is malformed")
    if action == "rollback" and rollback_from is None:
        raise LessonRevisionHistoryError("rollback revision is missing its source")
    if action != "rollback" and rollback_from is not None:
        raise LessonRevisionHistoryError("non-rollback revision has rollback metadata")

    return LessonRevision(
        lesson_id=lesson_id,
        revision=revision,
        canonical_fingerprint=fingerprint,
        occurred_at=occurred_at,
        action=action,
        relative_path=relative_path,
        markdown=markdown,
        reason=reason,
        rollback_from_revision=rollback_from,
    )


def _revision_to_dict(item: LessonRevision) -> dict[str, object]:
    return {
        "revision": item.revision,
        "canonical_fingerprint": item.canonical_fingerprint,
        "occurred_at": item.occurred_at,
        "action": item.action,
        "relative_path": item.relative_path,
        "markdown": item.markdown,
        "reason": item.reason,
        "rollback_from_revision": item.rollback_from_revision,
    }


class LessonRevisionHistoryStore:
    """Versioned JSON history with same-process locking and atomic replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, Any]:
        try:
            node = self.path.lstat()
        except FileNotFoundError:
            return _empty_document()
        except OSError as exc:
            raise LessonRevisionHistoryError("lesson revision history is unreadable") from exc

        if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
            raise LessonRevisionHistoryError("lesson revision history is unsafe")
        if node.st_size > MAX_HISTORY_BYTES:
            raise LessonRevisionHistoryError("lesson revision history exceeds size limits")

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LessonRevisionHistoryError("lesson revision history is unreadable") from exc

        if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
            raise LessonRevisionHistoryError("lesson revision history has an unsupported schema")
        lessons = raw.get("lessons")
        if not isinstance(lessons, dict):
            raise LessonRevisionHistoryError("lesson revision history is malformed")

        for lesson_id, entries in lessons.items():
            if not isinstance(lesson_id, str) or not lesson_id or not isinstance(entries, list):
                raise LessonRevisionHistoryError("lesson revision history is malformed")
            parsed = [_revision_from_dict(lesson_id, item) for item in entries]
            if [item.revision for item in parsed] != list(range(len(parsed))):
                raise LessonRevisionHistoryError(
                    "lesson revision numbers must be contiguous from zero"
                )
            if parsed and parsed[0].action != "baseline":
                raise LessonRevisionHistoryError(
                    "lesson revision history must start with a baseline"
                )
        return raw

    def _write(self, document: dict[str, Any]) -> None:
        try:
            serialized = (
                json.dumps(
                    document,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )
            encoded = serialized.encode("utf-8")
        except (TypeError, UnicodeError) as exc:
            raise LessonRevisionHistoryError(
                "lesson revision history could not be serialized"
            ) from exc

        if len(encoded) > MAX_HISTORY_BYTES:
            raise LessonRevisionHistoryError(
                "lesson revision history exceeds size limits"
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            temporary = None
        except (OSError, UnicodeError) as exc:
            raise LessonRevisionHistoryError(
                "lesson revision history could not be saved"
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def list(self, lesson_id: str) -> tuple[LessonRevision, ...]:
        with _LOCK:
            document = self._load()
            raw = document["lessons"].get(lesson_id, [])
            return tuple(_revision_from_dict(lesson_id, item) for item in raw)

    def get(self, lesson_id: str, revision: int) -> LessonRevision:
        revisions = self.list(lesson_id)
        if revision < 0 or revision >= len(revisions):
            raise LessonRevisionHistoryError("lesson revision was not found")
        return revisions[revision]

    def append(self, item: LessonRevision) -> LessonRevision:
        if not item.lesson_id:
            raise LessonRevisionHistoryError("lesson ID must not be blank")
        _revision_from_dict(item.lesson_id, _revision_to_dict(item))

        with _LOCK:
            document = self._load()
            entries = document["lessons"].setdefault(item.lesson_id, [])
            if not isinstance(entries, list):
                raise LessonRevisionHistoryError("lesson revision history is malformed")
            if item.revision != len(entries):
                raise LessonRevisionHistoryConflictError(
                    "lesson revision does not extend current history"
                )
            if item.revision == 0 and item.action != "baseline":
                raise LessonRevisionHistoryConflictError(
                    "first lesson revision must be a baseline"
                )
            if item.revision > 0 and item.action == "baseline":
                raise LessonRevisionHistoryConflictError(
                    "baseline is valid only for revision zero"
                )
            entries.append(_revision_to_dict(item))
            self._write(document)
        return item
