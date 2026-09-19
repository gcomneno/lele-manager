from __future__ import annotations

import json
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lele_manager.core.paths import data_dir


SCHEMA_VERSION = 1
CONTEXT_PACK_STORE_FILENAME = "context-packs.json"
MAX_BYTES = 32 * 1024 * 1024


class ContextPackStoreError(Exception):
    """Context Pack state cannot safely be read or written."""


class ContextPackNotFoundError(ContextPackStoreError):
    """The requested Context Pack does not exist."""


@dataclass(frozen=True, slots=True)
class ContextPack:
    id: str
    name: str
    vault_id: str
    lesson_ids: tuple[str, ...]
    created_at: str
    updated_at: str


def context_pack_store_path() -> Path:
    return data_dir() / CONTEXT_PACK_STORE_FILENAME


class ContextPackStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or context_pack_store_path()

    def create(
        self,
        *,
        name: str,
        vault_id: str,
        lesson_ids: tuple[str, ...],
    ) -> ContextPack:
        normalized_name = _normalize_name(name)
        normalized_vault_id = _normalize_vault_id(vault_id)
        normalized_lesson_ids = _normalize_lesson_ids(lesson_ids)

        now = _utc_now()
        pack = ContextPack(
            id=str(uuid.uuid4()),
            name=normalized_name,
            vault_id=normalized_vault_id,
            lesson_ids=normalized_lesson_ids,
            created_at=now,
            updated_at=now,
        )

        data = self._load()
        data["packs"].append(_pack_to_dict(pack))
        self._write(data)
        return pack

    def get(self, pack_id: str, *, vault_id: str | None = None) -> ContextPack:
        normalized_vault_id = (
            _normalize_vault_id(vault_id) if vault_id is not None else None
        )
        data = self._load()
        for raw in data["packs"]:
            pack = _pack_from_dict(raw)
            if pack.id == pack_id and (
                normalized_vault_id is None or pack.vault_id == normalized_vault_id
            ):
                return pack
        raise ContextPackNotFoundError("Context Pack was not found")

    def list(self, *, vault_id: str) -> tuple[ContextPack, ...]:
        normalized_vault_id = _normalize_vault_id(vault_id)
        return tuple(
            pack
            for raw in self._load()["packs"]
            if (pack := _pack_from_dict(raw)).vault_id == normalized_vault_id
        )

    def rename(
        self,
        pack_id: str,
        *,
        vault_id: str,
        name: str,
    ) -> ContextPack:
        current = self.get(pack_id, vault_id=vault_id)
        updated = ContextPack(
            id=current.id,
            name=_normalize_name(name),
            vault_id=current.vault_id,
            lesson_ids=current.lesson_ids,
            created_at=current.created_at,
            updated_at=_utc_now(),
        )
        self._replace_pack(updated)
        return updated

    def add_members(
        self,
        pack_id: str,
        *,
        vault_id: str,
        lesson_ids: tuple[str, ...],
    ) -> ContextPack:
        current = self.get(pack_id, vault_id=vault_id)
        additions = _normalize_lesson_ids(lesson_ids)

        if set(current.lesson_ids).intersection(additions):
            raise ContextPackStoreError(
                "Context Pack already contains one or more requested members"
            )

        updated = ContextPack(
            id=current.id,
            name=current.name,
            vault_id=current.vault_id,
            lesson_ids=current.lesson_ids + additions,
            created_at=current.created_at,
            updated_at=_utc_now(),
        )
        self._replace_pack(updated)
        return updated

    def remove_members(
        self,
        pack_id: str,
        *,
        vault_id: str,
        lesson_ids: tuple[str, ...],
    ) -> ContextPack:
        current = self.get(pack_id, vault_id=vault_id)
        removals = _normalize_lesson_ids(lesson_ids)
        removal_set = set(removals)

        updated = ContextPack(
            id=current.id,
            name=current.name,
            vault_id=current.vault_id,
            lesson_ids=tuple(
                lesson_id
                for lesson_id in current.lesson_ids
                if lesson_id not in removal_set
            ),
            created_at=current.created_at,
            updated_at=_utc_now(),
        )
        self._replace_pack(updated)
        return updated

    def delete(self, pack_id: str, *, vault_id: str) -> None:
        current = self.get(pack_id, vault_id=vault_id)
        data = self._load()
        data["packs"] = [
            raw
            for raw in data["packs"]
            if raw["id"] != current.id
        ]
        self._write(data)

    def _replace_pack(self, updated: ContextPack) -> None:
        data = self._load()
        replaced = False
        packs: list[dict[str, object]] = []

        for raw in data["packs"]:
            if raw["id"] == updated.id:
                packs.append(_pack_to_dict(updated))
                replaced = True
            else:
                packs.append(raw)

        if not replaced:
            raise ContextPackNotFoundError("Context Pack was not found")

        data["packs"] = packs
        self._write(data)

    def _load(self) -> dict[str, Any]:
        try:
            file_stat = self.path.lstat()
        except FileNotFoundError:
            return {
                "schema_version": SCHEMA_VERSION,
                "packs": [],
            }
        except OSError as exc:
            raise ContextPackStoreError(
                "Context Pack state cannot be inspected"
            ) from exc

        if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
            raise ContextPackStoreError(
                "Context Pack state must be a regular file"
            )

        if file_stat.st_size > MAX_BYTES:
            raise ContextPackStoreError("Context Pack state is too large")

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContextPackStoreError(
                "Context Pack state is unreadable"
            ) from exc

        if (
            not isinstance(raw, dict)
            or set(raw) != {"schema_version", "packs"}
            or raw.get("schema_version") != SCHEMA_VERSION
            or not isinstance(raw.get("packs"), list)
        ):
            raise ContextPackStoreError(
                "Context Pack state has an unsupported schema"
            )

        packs = raw["packs"]
        validated: list[dict[str, object]] = []
        seen_ids: set[str] = set()

        for item in packs:
            pack = _validate_stored_pack(item)
            if pack.id in seen_ids:
                raise ContextPackStoreError(
                    "Context Pack state contains duplicate pack ids"
                )
            seen_ids.add(pack.id)
            validated.append(_pack_to_dict(pack))

        return {
            "schema_version": SCHEMA_VERSION,
            "packs": validated,
        }

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
            raise ContextPackStoreError("Context Pack state could not be saved") from exc


def _pack_to_dict(pack: ContextPack) -> dict[str, object]:
    return {
        "id": pack.id,
        "name": pack.name,
        "vault_id": pack.vault_id,
        "lesson_ids": list(pack.lesson_ids),
        "created_at": pack.created_at,
        "updated_at": pack.updated_at,
    }


def _pack_from_dict(raw: dict[str, Any]) -> ContextPack:
    return _validate_stored_pack(raw)


def _validate_stored_pack(raw: object) -> ContextPack:
    if not isinstance(raw, dict):
        raise ContextPackStoreError("Context Pack entry is malformed")

    expected_keys = {
        "id",
        "name",
        "vault_id",
        "lesson_ids",
        "created_at",
        "updated_at",
    }
    if set(raw) != expected_keys:
        raise ContextPackStoreError("Context Pack entry is malformed")

    pack_id = raw["id"]
    name = raw["name"]
    vault_id = raw["vault_id"]
    lesson_ids = raw["lesson_ids"]
    created_at = raw["created_at"]
    updated_at = raw["updated_at"]

    if not isinstance(pack_id, str):
        raise ContextPackStoreError("Context Pack id is malformed")
    try:
        uuid.UUID(pack_id)
    except ValueError as exc:
        raise ContextPackStoreError("Context Pack id is malformed") from exc

    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise ContextPackStoreError("Context Pack name is malformed")

    normalized_vault_id = _normalize_vault_id(vault_id)

    if not isinstance(lesson_ids, list):
        raise ContextPackStoreError("Context Pack members are malformed")

    normalized_members: list[str] = []
    for lesson_id in lesson_ids:
        if (
            not isinstance(lesson_id, str)
            or not lesson_id.strip()
            or lesson_id != lesson_id.strip()
        ):
            raise ContextPackStoreError("Context Pack member is malformed")
        normalized_members.append(lesson_id)

    if len(set(normalized_members)) != len(normalized_members):
        raise ContextPackStoreError("Context Pack contains duplicate members")

    normalized_created_at = _validate_timestamp(created_at)
    normalized_updated_at = _validate_timestamp(updated_at)

    if normalized_updated_at < normalized_created_at:
        raise ContextPackStoreError(
            "Context Pack update timestamp precedes creation"
        )

    return ContextPack(
        id=pack_id,
        name=name,
        vault_id=normalized_vault_id,
        lesson_ids=tuple(normalized_members),
        created_at=created_at,
        updated_at=updated_at,
    )


def _validate_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ContextPackStoreError("Context Pack timestamp is malformed")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ContextPackStoreError(
            "Context Pack timestamp is malformed"
        ) from exc

    if parsed.utcoffset() is None:
        raise ContextPackStoreError(
            "Context Pack timestamp must be timezone-aware"
        )

    return parsed.astimezone(timezone.utc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ContextPackStoreError("Context Pack name is malformed")
    return name.strip()


def _normalize_vault_id(vault_id: str) -> str:
    if not isinstance(vault_id, str) or not vault_id.strip():
        raise ContextPackStoreError("Context Pack Vault id is malformed")
    normalized = vault_id.strip()
    try:
        uuid.UUID(normalized)
    except ValueError as exc:
        raise ContextPackStoreError("Context Pack Vault id is malformed") from exc
    return normalized


def _normalize_lesson_ids(lesson_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(lesson_ids, tuple) or not lesson_ids:
        raise ContextPackStoreError("Context Pack members are malformed")

    normalized: list[str] = []
    for lesson_id in lesson_ids:
        if not isinstance(lesson_id, str) or not lesson_id.strip():
            raise ContextPackStoreError("Context Pack member is malformed")
        normalized.append(lesson_id.strip())

    if len(set(normalized)) != len(normalized):
        raise ContextPackStoreError("Context Pack contains duplicate members")

    return tuple(normalized)
