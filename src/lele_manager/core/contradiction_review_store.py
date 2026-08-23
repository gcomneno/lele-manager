from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal, cast

from lele_manager.core.contradiction_review import (
    AuxiliaryDecision,
    GENERATOR_VERSION,
    PairIdentity,
    validate_auxiliary_decision,
)
from lele_manager.core.paths import data_dir


SCHEMA_VERSION = 1
CONTRADICTION_REVIEW_STORE_FILENAME = "contradiction-review-decisions.json"
_STORE_LOCK = Lock()


class ContradictionReviewStoreError(Exception):
    """Contradiction-review state cannot safely be read or written."""


@dataclass(frozen=True, slots=True)
class ContradictionReviewDecision:
    left_id: str
    right_id: str
    left_fingerprint: str
    right_fingerprint: str
    decision: AuxiliaryDecision
    decided_at: str
    note: str | None = None


def contradiction_review_decisions_path() -> Path:
    return data_dir() / CONTRADICTION_REVIEW_STORE_FILENAME


class ContradictionReviewStore:
    MAX_BYTES = 32 * 1024 * 1024

    def __init__(self, path: Path) -> None:
        self.path = path

    def is_suppressed(
        self, *, scope: str, left_id: str, left_fingerprint: str, right_id: str, right_fingerprint: str
    ) -> bool:
        try:
            pair, left_fingerprint, right_fingerprint = _normalized_pair_with_fingerprints(
                left_id, left_fingerprint, right_id, right_fingerprint
            )
        except ValueError:
            return False
        with _STORE_LOCK:
            data = self._load()
        entries = data["scopes"].get(scope, [])
        if not isinstance(entries, list):
            raise ContradictionReviewStoreError("contradiction-review scope is malformed")
        return any(
            entry["left_id"] == pair.left_id
            and entry["right_id"] == pair.right_id
            and entry["left_fingerprint"] == left_fingerprint
            and entry["right_fingerprint"] == right_fingerprint
            and entry["decision"] in ("different-context", "dismissed")
            for entry in entries
        )

    def save_decision(
        self,
        *,
        scope: str,
        left_id: str,
        left_fingerprint: str,
        right_id: str,
        right_fingerprint: str,
        decision: Literal["different-context", "dismissed"],
        note: str | None = None,
    ) -> ContradictionReviewDecision:
        if not isinstance(scope, str) or not scope.strip():
            raise ContradictionReviewStoreError("contradiction-review scope is malformed")
        try:
            pair, left_fingerprint, right_fingerprint = _normalized_pair_with_fingerprints(
                left_id, left_fingerprint, right_id, right_fingerprint
            )
            normalized_decision = validate_auxiliary_decision(decision)
        except ValueError as exc:
            raise ContradictionReviewStoreError("contradiction-review decision is malformed") from exc
        if note is not None and not isinstance(note, str):
            raise ContradictionReviewStoreError("contradiction-review note is malformed")

        stored = ContradictionReviewDecision(
            left_id=pair.left_id,
            right_id=pair.right_id,
            left_fingerprint=left_fingerprint,
            right_fingerprint=right_fingerprint,
            decision=normalized_decision,
            decided_at=datetime.now(timezone.utc).isoformat(),
            note=note,
        )
        with _STORE_LOCK:
            data = self._load()
            entries = data["scopes"].setdefault(scope, [])
            if not isinstance(entries, list):
                raise ContradictionReviewStoreError("contradiction-review scope is malformed")
            entries[:] = [
                entry
                for entry in entries
                if not (
                    isinstance(entry, dict)
                    and entry.get("left_id") == pair.left_id
                    and entry.get("right_id") == pair.right_id
                )
            ]
            entry = {
                "left_id": stored.left_id,
                "right_id": stored.right_id,
                "left_fingerprint": stored.left_fingerprint,
                "right_fingerprint": stored.right_fingerprint,
                "decision": stored.decision,
                "decided_at": stored.decided_at,
            }
            if stored.note is not None:
                entry["note"] = stored.note
            entries.append(entry)
            entries.sort(key=lambda item: (str(item.get("left_id")), str(item.get("right_id"))))
            self._write(data)
        return stored

    def _load(self) -> dict[str, Any]:
        try:
            node = self.path.lstat()
        except FileNotFoundError:
            return {"schema_version": SCHEMA_VERSION, "generator_version": GENERATOR_VERSION, "scopes": {}}
        except OSError as exc:
            raise ContradictionReviewStoreError("contradiction-review state is unreadable") from exc
        if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
            raise ContradictionReviewStoreError("contradiction-review state is unsafe")
        if node.st_size > self.MAX_BYTES:
            raise ContradictionReviewStoreError("contradiction-review state exceeds size limits")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContradictionReviewStoreError("contradiction-review state is unreadable") from exc
        _validate_store(data)
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
                temp_name = handle.name
            os.replace(temp_name, self.path)
        except OSError as exc:
            if temp_name is not None:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass
            raise ContradictionReviewStoreError("contradiction-review state could not be saved") from exc


def _normalized_pair_with_fingerprints(
    left_id: str, left_fingerprint: str, right_id: str, right_fingerprint: str
) -> tuple[PairIdentity, str, str]:
    if not left_fingerprint or not right_fingerprint:
        raise ValueError("fingerprints must be non-empty")
    pair = PairIdentity.from_ids(left_id, right_id)
    if pair.left_id == left_id.strip():
        return pair, left_fingerprint, right_fingerprint
    return pair, right_fingerprint, left_fingerprint


def _validate_store(data: Any) -> None:
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != SCHEMA_VERSION
        or data.get("generator_version") != GENERATOR_VERSION
        or not isinstance(data.get("scopes"), dict)
        or set(data) != {"schema_version", "generator_version", "scopes"}
    ):
        raise ContradictionReviewStoreError("contradiction-review state has an unsupported schema")
    for scope, entries in data["scopes"].items():
        if not isinstance(scope, str) or not scope.strip() or not isinstance(entries, list):
            raise ContradictionReviewStoreError("contradiction-review scope is malformed")
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            normalized = _validate_entry(entry)
            pair = (normalized["left_id"], normalized["right_id"])
            if pair in seen:
                raise ContradictionReviewStoreError("contradiction-review scope contains duplicate pair records")
            seen.add(pair)


def _validate_entry(entry: Any) -> dict[str, str]:
    expected = {"left_id", "right_id", "left_fingerprint", "right_fingerprint", "decision", "decided_at"}
    allowed = expected | {"note"}
    if not isinstance(entry, dict) or set(entry) - allowed or not expected.issubset(entry):
        raise ContradictionReviewStoreError("contradiction-review entry is malformed")
    if not all(isinstance(entry[key], str) and entry[key] for key in expected):
        raise ContradictionReviewStoreError("contradiction-review entry is malformed")
    if "note" in entry and not isinstance(entry["note"], str):
        raise ContradictionReviewStoreError("contradiction-review note is malformed")
    try:
        pair = PairIdentity.from_ids(entry["left_id"], entry["right_id"])
        validate_auxiliary_decision(entry["decision"])
        timestamp = datetime.fromisoformat(entry["decided_at"])
    except ValueError as exc:
        raise ContradictionReviewStoreError("contradiction-review entry is malformed") from exc
    if pair.as_tuple() != (entry["left_id"], entry["right_id"]):
        raise ContradictionReviewStoreError("contradiction-review entry pair is not canonical")
    offset = timestamp.utcoffset()
    if timestamp.tzinfo is None or offset is None or offset.total_seconds() != 0:
        raise ContradictionReviewStoreError("contradiction-review timestamp is malformed")
    return cast(dict[str, str], entry)
