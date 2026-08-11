"""Durable, vault-scoped decisions for duplicate review.

The path-derived scope is intentionally isolated here.  It is transitional
single-vault plumbing; #192 can replace it with a registered vault identity
without making duplicate-resolution callers aware of that migration.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Mapping
import unicodedata


_SCHEMA_VERSION = 2
_STORE_LOCK = Lock()


class DuplicateDecisionStoreError(Exception):
    """The decision state cannot safely be read or written."""


def _value(value: Any) -> str:
    return "" if value is None else str(value)


def _short(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFC", _value(value)).strip().split()).casefold()


def _text(value: Any) -> str:
    text = unicodedata.normalize("NFC", _value(value)).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _tags(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return sorted({_short(tag) for tag in value if _short(tag)})


def _date(value: Any) -> str:
    """Normalize projection timestamps and Markdown date strings identically."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    # Pandas Timestamp deliberately remains an implementation detail here.
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return _short(isoformat()[:10])
        except (TypeError, ValueError):
            pass
    return _short(value)


def material_fingerprint(lesson: Mapping[str, Any]) -> str:
    """Fingerprint the semantic snapshot used by duplicate review.

    Body line endings/trailing whitespace and short metadata casing/spacing use
    the same normalisation family as duplicate detection.  Tag membership is a
    set, so its presentation order is deliberately not material.
    """
    canonical = {
        "text": _text(lesson.get("text")),
        "title": _short(lesson.get("title")),
        "topic": _short(lesson.get("topic")),
        "source": _short(lesson.get("source")),
        "importance": _short(lesson.get("importance")),
        "tags": _tags(lesson.get("tags")),
        "date": _date(lesson.get("date")),
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def current_vault_scope(vault_dir: Path) -> str:
    """Legacy helper retained for callers outside the active runtime boundary."""
    return str(vault_dir.resolve())


@dataclass(frozen=True)
class DuplicateDecision:
    left_id: str
    right_id: str
    left_fingerprint: str
    right_fingerprint: str
    decided_at: str


def _normalised_pair(
    left_id: str, left_fingerprint: str, right_id: str, right_fingerprint: str
) -> tuple[str, str, str, str]:
    if left_id <= right_id:
        return left_id, right_id, left_fingerprint, right_fingerprint
    return right_id, left_id, right_fingerprint, left_fingerprint


class DuplicateDecisionStore:
    """Small JSON document with atomic writes and same-process locking."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": _SCHEMA_VERSION, "scopes": {}, "legacy_scopes": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DuplicateDecisionStoreError("duplicate decision state is unreadable") from exc
        if not isinstance(data, dict) or data.get("schema_version") not in (1, _SCHEMA_VERSION):
            raise DuplicateDecisionStoreError("duplicate decision state has an unsupported schema")
        if not isinstance(data.get("scopes"), dict):
            raise DuplicateDecisionStoreError("duplicate decision state is malformed")
        if data.get("schema_version") == 1:
            # Preserve every unmatched legacy path scope rather than losing a
            # user decision. Registry bootstrap migrates its known active path.
            return {"schema_version": _SCHEMA_VERSION, "scopes": {}, "legacy_scopes": data["scopes"]}
        if not isinstance(data.get("legacy_scopes", {}), dict):
            raise DuplicateDecisionStoreError("duplicate decision legacy state is malformed")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, prefix=f".{self.path.name}.", delete=False
            ) as handle:
                json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
                temp_name = handle.name
            os.replace(temp_name, self.path)
        except OSError as exc:
            try:
                Path(locals().get("temp_name", "")).unlink(missing_ok=True)
            except OSError:
                pass
            raise DuplicateDecisionStoreError("duplicate decision state could not be saved") from exc

    def migrate_legacy_scope(self, legacy_path_scope: str, vault_id: str) -> None:
        """Atomically map a v1 resolved-path scope to immutable Vault identity."""
        with _STORE_LOCK:
            data = self._load()
            legacy = data.setdefault("legacy_scopes", {})
            entries = legacy.pop(legacy_path_scope, None)
            if entries is not None:
                if not isinstance(entries, list):
                    raise DuplicateDecisionStoreError("duplicate decision legacy scope is malformed")
                destination = data.setdefault("scopes", {}).setdefault(vault_id, [])
                if not isinstance(destination, list):
                    raise DuplicateDecisionStoreError("duplicate decision scope is malformed")
                destination.extend(entries)
            self._write(data)

    def export_scope(self, scope: str) -> list[dict[str, str]]:
        """Return only one immutable Vault's decisions, never global state."""
        with _STORE_LOCK:
            data = self._load()
        entries = data["scopes"].get(scope, [])
        if not isinstance(entries, list):
            raise DuplicateDecisionStoreError("duplicate decision scope is malformed")
        expected = {"left_id", "right_id", "left_fingerprint", "right_fingerprint", "decided_at"}
        result: list[dict[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != expected or not all(isinstance(entry.get(key), str) for key in expected):
                raise DuplicateDecisionStoreError("duplicate decision scope is malformed")
            result.append({key: entry[key] for key in sorted(expected)})
        return sorted(result, key=lambda item: (item["left_id"], item["right_id"]))

    def replace_scope(self, scope: str, entries: list[dict[str, str]]) -> None:
        """Atomically replace one Vault scope without exposing other Vaults."""
        expected = {"left_id", "right_id", "left_fingerprint", "right_fingerprint", "decided_at"}
        normalized: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            if set(entry) != expected or not all(isinstance(entry.get(key), str) and entry[key] for key in expected):
                raise DuplicateDecisionStoreError("duplicate decision scope is malformed")
            pair = (entry["left_id"], entry["right_id"])
            if pair in seen or pair[0] >= pair[1]:
                raise DuplicateDecisionStoreError("duplicate decision scope is malformed")
            seen.add(pair)
            normalized.append({key: entry[key] for key in sorted(expected)})
        with _STORE_LOCK:
            data = self._load()
            data["scopes"][scope] = sorted(normalized, key=lambda item: (item["left_id"], item["right_id"]))
            self._write(data)

    def is_suppressed(
        self, *, scope: str, left_id: str, left_fingerprint: str, right_id: str, right_fingerprint: str
    ) -> bool:
        if not left_id or not right_id or left_id == right_id:
            return False
        left_id, right_id, left_fingerprint, right_fingerprint = _normalised_pair(
            left_id, left_fingerprint, right_id, right_fingerprint
        )
        with _STORE_LOCK:
            data = self._load()
        entries = data["scopes"].get(scope, [])
        if not isinstance(entries, list):
            raise DuplicateDecisionStoreError("duplicate decision scope is malformed")
        return any(
            isinstance(entry, dict)
            and entry.get("left_id") == left_id
            and entry.get("right_id") == right_id
            and entry.get("left_fingerprint") == left_fingerprint
            and entry.get("right_fingerprint") == right_fingerprint
            for entry in entries
        )

    def save_not_duplicates(
        self, *, scope: str, left_id: str, left_fingerprint: str, right_id: str, right_fingerprint: str
    ) -> DuplicateDecision:
        if not left_id or not right_id or left_id == right_id:
            raise DuplicateDecisionStoreError("a decision needs two distinct stable lesson IDs")
        left_id, right_id, left_fingerprint, right_fingerprint = _normalised_pair(
            left_id, left_fingerprint, right_id, right_fingerprint
        )
        decision = DuplicateDecision(
            left_id=left_id,
            right_id=right_id,
            left_fingerprint=left_fingerprint,
            right_fingerprint=right_fingerprint,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        with _STORE_LOCK:
            data = self._load()
            entries = data["scopes"].setdefault(scope, [])
            if not isinstance(entries, list):
                raise DuplicateDecisionStoreError("duplicate decision scope is malformed")
            entries[:] = [
                entry for entry in entries
                if not (
                    isinstance(entry, dict)
                    and entry.get("left_id") == left_id
                    and entry.get("right_id") == right_id
                )
            ]
            entries.append({
                "left_id": decision.left_id,
                "right_id": decision.right_id,
                "left_fingerprint": decision.left_fingerprint,
                "right_fingerprint": decision.right_fingerprint,
                "decided_at": decision.decided_at,
            })
            entries.sort(key=lambda item: (str(item.get("left_id")), str(item.get("right_id"))))
            self._write(data)
        return decision
