"""Persistent registry and immutable runtime context for managed Vaults.

The registry is deliberately small: Markdown remains the authority, while this
file only records stable identity and the selected workspace.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, List, cast

from .paths import cache_dir, data_dir
from .vault import DEFAULT_VAULT_DIRNAME, resolve_vault_dir

SCHEMA_VERSION = 1
_LOCK = RLock()


class VaultRegistryError(RuntimeError):
    code = "vault_registry_unavailable"


class VaultRegistryCorruptError(VaultRegistryError):
    code = "vault_registry_corrupt"


class VaultNotFoundError(VaultRegistryError):
    code = "vault_not_found"


class VaultPathError(VaultRegistryError):
    code = "vault_path_unavailable"


class VaultConflictError(VaultRegistryError):
    pass


class VaultMigrationConflictError(VaultRegistryError):
    code = "vault_migration_conflict"


@dataclass(frozen=True)
class RegisteredVault:
    id: str
    name: str
    path: Path
    registered_at: str


@dataclass(frozen=True)
class ActiveVaultContext:
    vault_id: str
    display_name: str
    vault_dir: Path
    projection_path: Path
    candidates_path: Path
    topic_model_path: Path
    duplicate_decision_scope: str


def registry_path() -> Path:
    return data_dir() / "vault-registry.json"


def _canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _record(value: Any) -> RegisteredVault:
    if not isinstance(value, dict):
        raise VaultRegistryCorruptError("vault registry entry is malformed")
    vault_id, name, path, registered_at = (value.get(k) for k in ("id", "name", "path", "registered_at"))
    if not all(isinstance(item, str) and item.strip() for item in (vault_id, name, path, registered_at)):
        raise VaultRegistryCorruptError("vault registry entry is malformed")
    try:
        uuid.UUID(vault_id)
    except ValueError as exc:
        raise VaultRegistryCorruptError("vault registry contains an invalid id") from exc
    return RegisteredVault(
        cast(str, vault_id), cast(str, name).strip(), _canonical(cast(str, path)), cast(str, registered_at)
    )


class VaultRegistryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or registry_path()

    def exists(self) -> bool:
        return self.path.exists()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise VaultNotFoundError("vault registry has not been initialized")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VaultRegistryCorruptError("vault registry is unreadable; it was left unchanged") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
            raise VaultRegistryCorruptError("vault registry has an unsupported schema")
        if not isinstance(raw.get("active_vault_id"), str) or not isinstance(raw.get("vaults"), list):
            raise VaultRegistryCorruptError("vault registry is malformed")
        vaults = [_record(item) for item in raw["vaults"]]
        if not vaults or raw["active_vault_id"] not in {item.id for item in vaults}:
            raise VaultRegistryCorruptError("vault registry has no valid active Vault")
        self._validate_unique(vaults)
        return {"schema_version": SCHEMA_VERSION, "active_vault_id": raw["active_vault_id"], "vaults": vaults}

    @staticmethod
    def _validate_unique(vaults: list[RegisteredVault]) -> None:
        if len({item.id for item in vaults}) != len(vaults):
            raise VaultRegistryCorruptError("vault registry contains duplicate ids")
        names = [item.name.casefold() for item in vaults]
        if len(set(names)) != len(names):
            raise VaultRegistryCorruptError("vault registry contains duplicate names")
        for index, left in enumerate(vaults):
            for right in vaults[index + 1:]:
                if left.path == right.path:
                    raise VaultRegistryCorruptError("vault registry contains duplicate paths")
                if left.path in right.path.parents or right.path in left.path.parents:
                    raise VaultRegistryCorruptError("vault registry contains overlapping paths")

    def _write(self, data: dict[str, Any]) -> None:
        serializable = {
            "schema_version": SCHEMA_VERSION,
            "active_vault_id": data["active_vault_id"],
            "vaults": [
                {"id": item.id, "name": item.name, "path": str(item.path), "registered_at": item.registered_at}
                for item in sorted(data["vaults"], key=lambda item: item.id)
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, prefix=f".{self.path.name}.", delete=False) as output:
                json.dump(serializable, output, ensure_ascii=False, sort_keys=True, indent=2)
                output.write("\n")
                temp_name = output.name
            os.replace(temp_name, self.path)
        except OSError as exc:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)
            raise VaultRegistryError("vault registry could not be saved") from exc

    def bootstrap(self) -> RegisteredVault:
        """Persist the legacy source only when no registry exists."""
        with _LOCK:
            if self.path.exists():
                return self.active()
            source = resolve_vault_dir()  # env is intentionally consulted only here
            name = source.name or DEFAULT_VAULT_DIRNAME
            item = RegisteredVault(str(uuid.uuid4()), name, source, datetime.now(timezone.utc).isoformat())
            self._write({"active_vault_id": item.id, "vaults": [item]})
            self._migrate_legacy_candidates(item)
            from .duplicate_decisions import DuplicateDecisionStore
            DuplicateDecisionStore(data_dir() / "duplicate-decisions.json").migrate_legacy_scope(str(item.path), item.id)
            return item

    def list(self) -> list[RegisteredVault]:
        with _LOCK:
            return list(self._load()["vaults"])

    def active(self) -> RegisteredVault:
        with _LOCK:
            data = self._load()
        return next(item for item in data["vaults"] if item.id == data["active_vault_id"])

    def context(self, *, bootstrap: bool = True) -> ActiveVaultContext:
        item = self.bootstrap() if bootstrap and not self.exists() else self.active()
        return self.context_for(item)

    @staticmethod
    def context_for(item: RegisteredVault) -> ActiveVaultContext:
        return ActiveVaultContext(item.id, item.name, item.path, data_dir() / "vaults" / item.id / "lessons.jsonl", data_dir() / "vaults" / item.id / "candidates.json", cache_dir() / "vaults" / item.id / "topic_model.joblib", item.id)

    def _assert_new(self, name: str, path: Path, vaults: List[RegisteredVault]) -> None:
        if not name.strip():
            raise VaultConflictError("vault_name_conflict: Vault name must not be blank")
        if any(item.name.casefold() == name.strip().casefold() for item in vaults):
            raise VaultConflictError("vault_name_conflict: Vault name is already registered")
        for item in vaults:
            if item.path == path:
                raise VaultConflictError("vault_path_already_registered: Vault path is already registered")
            if item.path in path.parents or path in item.path.parents:
                raise VaultConflictError("vault_path_overlaps_registered: Vault path overlaps another registered Vault")

    def register(self, name: str, path: str | Path) -> RegisteredVault:
        resolved = _canonical(path)
        if not resolved.is_dir():
            raise VaultPathError("Vault path is not an existing directory")
        with _LOCK:
            data = self._load()
            self._assert_new(name, resolved, data["vaults"])
            item = RegisteredVault(str(uuid.uuid4()), name.strip(), resolved, datetime.now(timezone.utc).isoformat())
            data["vaults"].append(item)
            self._write(data)
        return item

    def create(self, name: str, path: str | Path) -> RegisteredVault:
        resolved = _canonical(path)
        if resolved.exists() and (not resolved.is_dir() or any(resolved.iterdir())):
            raise VaultConflictError("vault_path_unavailable: create requires a new or empty directory")
        resolved.mkdir(parents=True, exist_ok=True)
        return self.register(name, resolved)

    def rename(self, vault_id: str, name: str) -> RegisteredVault:
        with _LOCK:
            data = self._load()
            item = next((item for item in data["vaults"] if item.id == vault_id), None)
            if item is None:
                raise VaultNotFoundError("Vault was not found")
            others = [entry for entry in data["vaults"] if entry.id != vault_id]
            self._assert_new(name, item.path, others)
            replacement = RegisteredVault(item.id, name.strip(), item.path, item.registered_at)
            data["vaults"] = [replacement if entry.id == vault_id else entry for entry in data["vaults"]]
            self._write(data)
        return replacement

    def remove(self, vault_id: str) -> None:
        with _LOCK:
            data = self._load()
            if data["active_vault_id"] == vault_id:
                raise VaultConflictError("active_vault_cannot_be_removed: Activate another Vault first")
            if not any(item.id == vault_id for item in data["vaults"]):
                raise VaultNotFoundError("Vault was not found")
            data["vaults"] = [item for item in data["vaults"] if item.id != vault_id]
            self._write(data)

    def activate(self, vault_id: str) -> RegisteredVault:
        with _LOCK:
            data = self._load()
            item = next((item for item in data["vaults"] if item.id == vault_id), None)
            if item is None:
                raise VaultNotFoundError("Vault was not found")
            if not item.path.is_dir():
                raise VaultPathError("Vault path is unavailable")
            data["active_vault_id"] = vault_id
            self._write(data)
            return item

    def _migrate_legacy_candidates(self, item: RegisteredVault) -> None:
        legacy, target = data_dir() / "candidates.json", data_dir() / "vaults" / item.id / "candidates.json"
        if legacy.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(legacy, target)
            except OSError as exc:
                raise VaultMigrationConflictError("legacy candidate staging could not be migrated") from exc
        elif legacy.exists() and target.exists():
            raise VaultMigrationConflictError("legacy and scoped candidate staging both exist")


def active_vault_context() -> ActiveVaultContext:
    return VaultRegistryStore().context()
