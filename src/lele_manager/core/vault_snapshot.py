"""Portable, validated, per-Vault snapshot and exact restore support.

The ZIP reader in this module deliberately treats every archive as hostile.  A
snapshot is validated completely and staged outside the Vault before a restore
is allowed to change canonical Markdown or scoped editorial state.
"""
from __future__ import annotations

import hashlib
import inspect
import io
import json
import os
import stat
import tempfile
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.core.duplicate_decisions import DuplicateDecisionStore
from lele_manager.core.json_compat import canonical_json
from lele_manager.core.vault_registry import ActiveVaultContext


FORMAT = "lele-vault-snapshot"
SCHEMA_VERSION = 1
RESTORE_SEMANTICS_VERSION = 1
MANIFEST_MEMBER = "manifest.json"
CANONICAL_PREFIX = "canonical/"
CANDIDATES_MEMBER = "editorial/candidates.json"
DUPLICATES_MEMBER = "editorial/duplicate-decisions.json"
MAX_MEMBERS = 10_000
MAX_MEMBER_SIZE = 32 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 256 * 1024 * 1024
MAX_ARTIFACT_SIZE = 300 * 1024 * 1024


class VaultSnapshotError(RuntimeError):
    code = "snapshot_error"


class SnapshotValidationError(VaultSnapshotError):
    code = "snapshot_invalid"


class SnapshotPlanStaleError(VaultSnapshotError):
    code = "snapshot_plan_stale"


class SnapshotTargetError(VaultSnapshotError):
    code = "snapshot_target_unavailable"


class SnapshotRestoreError(VaultSnapshotError):
    code = "snapshot_restore_failed"

    def __init__(self, message: str, *, rollback_succeeded: bool) -> None:
        super().__init__(message)
        self.rollback_succeeded = rollback_succeeded


@dataclass(frozen=True)
class SnapshotFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ValidatedSnapshot:
    raw: bytes
    artifact_sha256: str
    source_vault_id: str
    source_vault_name: str
    created_at: str
    canonical: tuple[SnapshotFile, ...]
    candidates: bytes
    duplicate_decisions: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class RestorePreview:
    plan_digest: str
    target_vault_id: str
    target_name: str
    target_path: str
    source_vault_id: str
    source_vault_name: str
    canonical_file_count: int
    additions: tuple[str, ...]
    replacements: tuple[str, ...]
    removals: tuple[str, ...]
    unchanged: tuple[str, ...]
    editorial_state: tuple[str, ...]
    derived_effects: tuple[str, ...]


@dataclass(frozen=True)
class RestoreResult:
    canonical_restored: bool
    rollback_succeeded: bool | None
    derived_reconciled: bool
    derived_error: str | None
    preview: RestorePreview


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def _safe_member_name(name: str) -> None:
    if not name or "\x00" in name or "\\" in name:
        raise SnapshotValidationError("archive member path is invalid")
    if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
        raise SnapshotValidationError("archive member path is absolute")
    raw_parts = name.split("/")
    windows_devices = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if any(
        part in ("", ".", "..")
        or any(char in part for char in '<>:"|?*')
        or part.endswith((".", " "))
        or part.split(".", 1)[0].upper() in windows_devices
        for part in raw_parts
    ):
        raise SnapshotValidationError("archive member path escapes the snapshot namespace")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise SnapshotValidationError("archive member path escapes the snapshot namespace")


def _zip_member_is_regular(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    return file_type in (0, stat.S_IFREG)


def _read_archive_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """Read one already-described member without trusting ZIP metadata alone."""
    if info.file_size > MAX_MEMBER_SIZE:
        raise SnapshotValidationError("snapshot member exceeds size limit")
    chunks: list[bytes] = []
    total = 0
    try:
        with archive.open(info, "r") as member:
            while chunk := member.read(min(1024 * 1024, MAX_MEMBER_SIZE - total + 1)):
                total += len(chunk)
                if total > MAX_MEMBER_SIZE or total > info.file_size:
                    raise SnapshotValidationError("snapshot member exceeds actual size limit")
                chunks.append(chunk)
    except (OSError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        raise SnapshotValidationError("snapshot member could not be safely read") from exc
    if total != info.file_size:
        raise SnapshotValidationError("snapshot member size does not match its ZIP metadata")
    return b"".join(chunks)


def _json_load(raw: bytes, label: str) -> Any:
    def duplicate_reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=duplicate_reject)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError(f"{label} is not valid JSON") from exc


def read_canonical_markdown_files(vault_dir: Path) -> dict[str, bytes]:
    """Return the maintained canonical Markdown namespace without following links.

    The maintained Vault importer and tree both recurse over every ``*.md``
    file below the Vault root.  Consequently every such regular file is
    canonical managed state; non-Markdown files are outside this boundary.
    """
    if not vault_dir.is_dir() or vault_dir.is_symlink():
        raise SnapshotTargetError("registered Vault directory is unavailable or unsafe")
    result: dict[str, bytes] = {}
    total = 0
    root = vault_dir.resolve()

    def visit(directory: Path, relative: PurePosixPath) -> None:
        nonlocal total
        try:
            entries = sorted(directory.iterdir(), key=lambda path: path.name)
        except OSError as exc:
            raise SnapshotTargetError("Vault directory could not be safely read") from exc
        for path in entries:
            rel = relative / path.name
            try:
                node = path.lstat()
            except OSError as exc:
                raise SnapshotTargetError("Vault entry could not be safely inspected") from exc
            if stat.S_ISLNK(node.st_mode):
                raise SnapshotTargetError("Vault contains a symlinked entry")
            if stat.S_ISDIR(node.st_mode):
                visit(path, rel)
            elif stat.S_ISREG(node.st_mode):
                if path.suffix.lower() == ".md":
                    if node.st_size > MAX_MEMBER_SIZE or total + node.st_size > MAX_UNCOMPRESSED_SIZE:
                        raise SnapshotTargetError("Vault state exceeds snapshot size limits")
                    try:
                        data = _read_bounded_regular_file(path, node, "Vault Markdown")
                    except OSError as exc:
                        raise SnapshotTargetError("Vault Markdown could not be safely read") from exc
                    if total + len(data) > MAX_UNCOMPRESSED_SIZE:
                        raise SnapshotTargetError("Vault state exceeds snapshot size limits")
                    total += len(data)
                    result[rel.as_posix()] = data
            else:
                # Refuse unusual filesystem nodes rather than leaving an
                # ambiguous snapshot boundary around FIFOs/devices/sockets.
                raise SnapshotTargetError("Vault contains an unsupported special filesystem entry")

    visit(root, PurePosixPath())
    return dict(sorted(result.items()))


def _validate_markdown_payload(files: Mapping[str, bytes]) -> None:
    """Validate the portable canonical namespace without rewriting its bytes.

    Vault Doctor may report editorial/metadata defects in Markdown that the
    maintained importer still treats as canonical source. A snapshot is a
    backup boundary, not a repair operation, so it must preserve that managed
    state exactly instead of rejecting it or normalising it on restore.
    """
    portable: set[str] = set()
    for rel, contents in files.items():
        if not isinstance(rel, str) or not rel.lower().endswith(".md") or not isinstance(contents, bytes):
            raise SnapshotValidationError("snapshot canonical payload is malformed")
        _safe_member_name(rel)
        normalized = unicodedata.normalize("NFC", rel).casefold()
        if normalized in portable:
            raise SnapshotValidationError("snapshot canonical paths are not portable")
        portable.add(normalized)


def _read_bounded_regular_file(path: Path, node: os.stat_result, label: str) -> bytes:
    """Read a regular file only after a size check, including growth races."""
    if not stat.S_ISREG(node.st_mode) or stat.S_ISLNK(node.st_mode) or node.st_size > MAX_MEMBER_SIZE:
        raise SnapshotTargetError(f"{label} exceeds snapshot size limits or is unsafe")
    chunks: list[bytes] = []
    total = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(min(1024 * 1024, MAX_MEMBER_SIZE - total + 1)):
                total += len(chunk)
                if total > MAX_MEMBER_SIZE:
                    raise SnapshotTargetError(f"{label} exceeds snapshot size limits")
                chunks.append(chunk)
    except OSError as exc:
        raise SnapshotTargetError(f"{label} could not be safely read") from exc
    return b"".join(chunks)


def _scoped_root(path: Path) -> Path:
    """Return the data/cache root for the fixed ``root/vaults/id/file`` layout."""
    try:
        return path.parents[2]
    except IndexError as exc:  # defensive only; contexts are registry-owned
        raise SnapshotTargetError("managed scoped path is malformed") from exc


def _assert_safe_scoped_path(path: Path, label: str, *, create_parents: bool = False) -> Path:
    """Check a managed data/cache path without following substituted links."""
    root = _scoped_root(path)
    try:
        root_node = root.lstat()
    except FileNotFoundError:
        if not create_parents:
            return path
        root.mkdir(parents=True, exist_ok=True)
        root_node = root.lstat()
    except OSError as exc:
        raise SnapshotTargetError(f"{label} could not be safely inspected") from exc
    if stat.S_ISLNK(root_node.st_mode) or not stat.S_ISDIR(root_node.st_mode):
        raise SnapshotTargetError(f"{label} managed root is unsafe")
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current = current / part
        try:
            node = current.lstat()
        except FileNotFoundError:
            if not create_parents:
                return path
            current.mkdir()
            node = current.lstat()
        except OSError as exc:
            raise SnapshotTargetError(f"{label} could not be safely inspected") from exc
        if stat.S_ISLNK(node.st_mode) or not stat.S_ISDIR(node.st_mode):
            raise SnapshotTargetError(f"{label} managed directory is unsafe")
    try:
        node = path.lstat()
    except FileNotFoundError:
        return path
    except OSError as exc:
        raise SnapshotTargetError(f"{label} could not be safely inspected") from exc
    if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
        raise SnapshotTargetError(f"{label} is unsafe")
    return path


def prepare_scoped_mutation_path(path: Path, label: str) -> Path:
    """Create only verified managed parents at an actual mutation boundary."""
    return _assert_safe_scoped_path(path, label, create_parents=True)


def invalidate_scoped_derived_artifact(path: Path, label: str) -> None:
    path = _assert_safe_scoped_path(path, label, create_parents=False)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise SnapshotTargetError(f"{label} could not be invalidated") from exc


def _validate_candidates(raw: bytes, staging: Path) -> None:
    path = staging / "candidates.json"
    path.write_bytes(raw)
    # Listing applies the maintained, versioned candidate persistence parser.
    try:
        JsonCandidateRepository(path).list()
    except Exception as exc:
        raise SnapshotValidationError("snapshot candidate staging is malformed") from exc


def _read_regular_state_file(path: Path, label: str) -> bytes | None:
    """Read optional editorial state without accepting a symlink as authority."""
    _assert_safe_scoped_path(path, label)
    try:
        node = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SnapshotTargetError(f"{label} could not be safely inspected") from exc
    if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
        raise SnapshotTargetError(f"{label} is unsafe")
    try:
        return _read_bounded_regular_file(path, node, label)
    except OSError as exc:
        raise SnapshotTargetError(f"{label} could not be safely read") from exc


def _validate_decisions(value: Any) -> tuple[dict[str, str], ...]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "decisions"}:
        raise SnapshotValidationError("snapshot duplicate decisions are malformed")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1 or not isinstance(value["decisions"], list):
        raise SnapshotValidationError("snapshot duplicate decisions have an unsupported schema")
    expected = {"left_id", "right_id", "left_fingerprint", "right_fingerprint", "decided_at"}
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for decision in value["decisions"]:
        if not isinstance(decision, dict) or set(decision) != expected:
            raise SnapshotValidationError("snapshot duplicate decision is malformed")
        if not all(isinstance(decision[key], str) and decision[key] for key in expected):
            raise SnapshotValidationError("snapshot duplicate decision is malformed")
        pair = (decision["left_id"], decision["right_id"])
        if pair in seen or pair[0] >= pair[1]:
            raise SnapshotValidationError("snapshot duplicate decisions are not canonical")
        seen.add(pair)
        results.append({key: decision[key] for key in sorted(expected)})
    return tuple(sorted(results, key=lambda item: (item["left_id"], item["right_id"])))


def create_snapshot(context: ActiveVaultContext, decisions: DuplicateDecisionStore) -> bytes:
    """Create a portable snapshot without changing registry selection or state."""
    canonical = read_canonical_markdown_files(context.vault_dir)
    _validate_markdown_payload(canonical)
    stored_candidates = _read_regular_state_file(context.candidates_path, "candidate state")
    if stored_candidates is not None:
        candidates = stored_candidates
        with tempfile.TemporaryDirectory(prefix="lele-snapshot-candidates-") as temporary:
            _validate_candidates(candidates, Path(temporary))
    else:
        candidates = _canonical_bytes({"candidates": [], "schema_version": 2})
    try:
        scoped_decisions = decisions.export_scope(context.duplicate_decision_scope)
    except Exception as exc:
        raise SnapshotValidationError("duplicate decision state is malformed") from exc
    decisions_bytes = _canonical_bytes({"schema_version": 1, "decisions": scoped_decisions})
    payload: dict[str, bytes] = {
        f"{CANONICAL_PREFIX}{rel}": contents for rel, contents in canonical.items()
    }
    payload[CANDIDATES_MEMBER] = candidates
    payload[DUPLICATES_MEMBER] = decisions_bytes
    if len(payload) + 1 > MAX_MEMBERS or any(len(data) > MAX_MEMBER_SIZE for data in payload.values()):
        raise SnapshotValidationError("Vault state exceeds snapshot size limits")
    if sum(len(data) for data in payload.values()) > MAX_UNCOMPRESSED_SIZE:
        raise SnapshotValidationError("Vault state exceeds snapshot size limits")
    inventory = [
        {"path": name, "size": len(data), "sha256": _digest(data)}
        for name, data in sorted(payload.items())
    ]
    manifest = {
        "canonical_files": [rel for rel in canonical],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "editorial_state": ["candidates", "duplicate_decisions"],
        "files": inventory,
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "source_vault": {"id": context.vault_id, "name": context.display_name},
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(payload):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(info, payload[name])
        info = zipfile.ZipInfo(MANIFEST_MEMBER, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (stat.S_IFREG | 0o600) << 16
        archive.writestr(info, _canonical_bytes(manifest))
    artifact = output.getvalue()
    if len(artifact) > MAX_ARTIFACT_SIZE:
        raise SnapshotValidationError("Vault snapshot exceeds artifact size limit")
    return artifact


def validate_snapshot(raw: bytes) -> ValidatedSnapshot:
    """Read and fully validate a ZIP artifact before target state is inspected."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ARTIFACT_SIZE:
        raise SnapshotValidationError("snapshot artifact is empty")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (OSError, zipfile.BadZipFile) as exc:
        raise SnapshotValidationError("snapshot artifact is not a valid ZIP archive") from exc
    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_MEMBERS:
            raise SnapshotValidationError("snapshot has an unreasonable member count")
        names = [info.filename for info in infos]
        if len(set(names)) != len(names) or names.count(MANIFEST_MEMBER) != 1:
            raise SnapshotValidationError("snapshot must contain exactly one manifest")
        # Snapshots are portable between the supported case-sensitive and
        # case-insensitive filesystem configurations.  NFC/casefold aliases
        # would otherwise make destination identity platform-dependent.
        normalized_names = [unicodedata.normalize("NFC", name).casefold() for name in names]
        if len(set(normalized_names)) != len(normalized_names):
            raise SnapshotValidationError("snapshot contains case-colliding member paths")
        normalized_name_set = set(normalized_names)
        if any(
            "/".join(name.split("/")[:index]) in normalized_name_set
            for name in normalized_names
            for index in range(1, len(name.split("/")))
        ):
            raise SnapshotValidationError("snapshot contains directory/file path collisions")
        total = 0
        for info in infos:
            _safe_member_name(info.filename)
            if info.is_dir() or not _zip_member_is_regular(info):
                raise SnapshotValidationError("snapshot contains a non-regular archive member")
            if info.flag_bits & 0x1:
                raise SnapshotValidationError("encrypted snapshot members are unsupported")
            if info.file_size < 0 or info.file_size > MAX_MEMBER_SIZE:
                raise SnapshotValidationError("snapshot member exceeds size limit")
            total += info.file_size
        if total > MAX_UNCOMPRESSED_SIZE:
            raise SnapshotValidationError("snapshot exceeds uncompressed size limit")
        by_name = {info.filename: info for info in infos}
        contents = {name: _read_archive_member(archive, info) for name, info in by_name.items()}
        manifest = _json_load(contents[MANIFEST_MEMBER], "snapshot manifest")
        required = {"format", "schema_version", "created_at", "source_vault", "files", "canonical_files", "editorial_state"}
        if not isinstance(manifest, dict) or set(manifest) != required:
            raise SnapshotValidationError("snapshot manifest is malformed")
        if (
            not isinstance(manifest["format"], str)
            or type(manifest["schema_version"]) is not int
            or manifest["format"] != FORMAT
            or manifest["schema_version"] != SCHEMA_VERSION
        ):
            raise SnapshotValidationError("snapshot format or schema version is unsupported")
        if not isinstance(manifest["created_at"], str) or not manifest["created_at"]:
            raise SnapshotValidationError("snapshot creation timestamp is malformed")
        try:
            datetime.fromisoformat(manifest["created_at"])
        except ValueError as exc:
            raise SnapshotValidationError("snapshot creation timestamp is malformed") from exc
        source = manifest["source_vault"]
        if not isinstance(source, dict) or set(source) != {"id", "name"} or not all(isinstance(source.get(k), str) for k in ("id", "name")):
            raise SnapshotValidationError("snapshot source provenance is malformed")
        try:
            uuid.UUID(source["id"])
        except ValueError as exc:
            raise SnapshotValidationError("snapshot source provenance is malformed") from exc
        files = manifest["files"]
        if not isinstance(files, list):
            raise SnapshotValidationError("snapshot inventory is malformed")
        inventory: dict[str, SnapshotFile] = {}
        for record in files:
            if not isinstance(record, dict) or set(record) != {"path", "size", "sha256"}:
                raise SnapshotValidationError("snapshot inventory record is malformed")
            name, size, digest = record["path"], record["size"], record["sha256"]
            if not isinstance(name, str) or type(size) is not int or size < 0 or not isinstance(digest, str) or len(digest) != 64:
                raise SnapshotValidationError("snapshot inventory record is malformed")
            _safe_member_name(name)
            if name in inventory:
                raise SnapshotValidationError("snapshot inventory contains duplicate paths")
            inventory[name] = SnapshotFile(name, size, digest)
        if [entry["path"] for entry in files] != sorted(inventory):
            raise SnapshotValidationError("snapshot inventory is not deterministically ordered")
        actual = set(names) - {MANIFEST_MEMBER}
        if set(inventory) != actual:
            raise SnapshotValidationError("snapshot has undeclared or missing archive entries")
        for name, entry in inventory.items():
            content = contents[name]
            if len(content) != entry.size or _digest(content) != entry.sha256:
                raise SnapshotValidationError("snapshot inventory checksum or size does not match")
        canonical_paths = manifest["canonical_files"]
        if not isinstance(canonical_paths, list) or not all(isinstance(path, str) for path in canonical_paths):
            raise SnapshotValidationError("snapshot canonical inventory is malformed")
        if (
            len(set(canonical_paths)) != len(canonical_paths)
            or canonical_paths != sorted(canonical_paths)
            or len({unicodedata.normalize("NFC", path).casefold() for path in canonical_paths}) != len(canonical_paths)
        ):
            raise SnapshotValidationError("snapshot canonical inventory is malformed")
        canonical: list[SnapshotFile] = []
        for rel in canonical_paths:
            if not isinstance(rel, str) or not rel.lower().endswith(".md"):
                raise SnapshotValidationError("snapshot canonical path is invalid")
            _safe_member_name(rel)
            member = f"{CANONICAL_PREFIX}{rel}"
            if member not in inventory:
                raise SnapshotValidationError("snapshot canonical file is absent from inventory")
            canonical.append(SnapshotFile(rel, inventory[member].size, inventory[member].sha256))
        expected_members = {f"{CANONICAL_PREFIX}{item.path}" for item in canonical} | {CANDIDATES_MEMBER, DUPLICATES_MEMBER}
        if set(inventory) != expected_members:
            raise SnapshotValidationError("snapshot contains unsupported payload members")
        if manifest["editorial_state"] != ["candidates", "duplicate_decisions"]:
            raise SnapshotValidationError("snapshot editorial state inventory is unsupported")
        canonical_bytes = {item.path: contents[f"{CANONICAL_PREFIX}{item.path}"] for item in canonical}
        candidates = contents[CANDIDATES_MEMBER]
        duplicate_decisions = _validate_decisions(_json_load(contents[DUPLICATES_MEMBER], "snapshot duplicate decisions"))
    with tempfile.TemporaryDirectory(prefix="lele-snapshot-validation-") as temporary:
        _validate_markdown_payload(canonical_bytes)
        _validate_candidates(candidates, Path(temporary))
    return ValidatedSnapshot(raw, _digest(raw), source["id"], source["name"], manifest["created_at"], tuple(canonical), candidates, duplicate_decisions)


def _target_state_digest(context: ActiveVaultContext, decisions: DuplicateDecisionStore) -> str:
    canonical = read_canonical_markdown_files(context.vault_dir)
    candidates = _read_regular_state_file(context.candidates_path, "candidate state") or b""
    state = {
        "canonical": [{"path": path, "sha256": _digest(data)} for path, data in canonical.items()],
        "candidates_sha256": _digest(candidates),
        "decisions": decisions.export_scope(context.duplicate_decision_scope),
    }
    return _digest(_canonical_bytes(state))


def _preview_digest(validated: ValidatedSnapshot, context: ActiveVaultContext, target_state: str) -> str:
    return _digest(_canonical_bytes({
        "artifact": validated.artifact_sha256,
        "restore_semantics_version": RESTORE_SEMANTICS_VERSION,
        "target_id": context.vault_id,
        "target_name": context.display_name,
        "target_path": str(context.vault_dir),
        "projection_path": str(context.projection_path),
        "candidates_path": str(context.candidates_path),
        "topic_model_path": str(context.topic_model_path),
        "duplicate_decision_scope": context.duplicate_decision_scope,
        "target_state": target_state,
    }))


def preview_restore(validated: ValidatedSnapshot, context: ActiveVaultContext, decisions: DuplicateDecisionStore) -> RestorePreview:
    current = read_canonical_markdown_files(context.vault_dir)
    with zipfile.ZipFile(io.BytesIO(validated.raw)) as archive:
        incoming = {item.path: archive.read(f"{CANONICAL_PREFIX}{item.path}") for item in validated.canonical}
    additions = tuple(sorted(set(incoming) - set(current)))
    removals = tuple(sorted(set(current) - set(incoming)))
    replacements = tuple(sorted(path for path in set(current) & set(incoming) if current[path] != incoming[path]))
    unchanged = tuple(sorted(path for path in set(current) & set(incoming) if current[path] == incoming[path]))
    plan = _preview_digest(validated, context, _target_state_digest(context, decisions))
    return RestorePreview(plan, context.vault_id, context.display_name, str(context.vault_dir), validated.source_vault_id, validated.source_vault_name, len(incoming), additions, replacements, removals, unchanged, ("candidate staging", "duplicate decisions"), ("projection rebuilt", "similarity cache invalidated", "topic model invalidated"))


def _assert_safe_destination(root: Path, rel: str) -> Path:
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise SnapshotTargetError("registered Vault directory is unavailable") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise SnapshotTargetError("registered Vault directory is unavailable or unsafe")
    target = root / rel
    parent = root
    for part in PurePosixPath(rel).parts[:-1]:
        parent = parent / part
        if parent.exists() and parent.is_symlink():
            raise SnapshotTargetError("target Vault contains a symlinked destination directory")
    if target.exists() and target.is_symlink():
        raise SnapshotTargetError("target Vault contains a symlinked Markdown destination")
    resolved_parent = target.parent.resolve()
    try:
        resolved_parent.relative_to(root.resolve())
    except ValueError as exc:
        raise SnapshotTargetError("target destination escapes registered Vault") from exc
    return target


def validate_new_canonical_destination(root: Path, relative_path: str) -> Path:
    """Validate a new canonical target without creating files or directories.

    Cross-Vault workflows use this narrow boundary instead of trusting a
    source-relative path as a filesystem path.  The caller must still use
    :func:`write_new_canonical_file` at its mutation boundary because another
    process can occupy a name after this validation.
    """
    target = _assert_safe_destination(root, relative_path)
    try:
        target.lstat()
    except FileNotFoundError:
        return target
    except OSError as exc:
        raise SnapshotTargetError("target Vault destination could not be safely inspected") from exc
    raise SnapshotTargetError("target Vault canonical destination is occupied")


def write_new_canonical_file(root: Path, relative_path: str, data: bytes) -> Path:
    """Atomically create, never replace, one safe canonical Markdown file."""
    target = validate_new_canonical_destination(root, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = validate_new_canonical_destination(root, relative_path)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # link(2) is deliberately used instead of replace(2): a late
        # collision is a controlled failure, never an implicit overwrite.
        target = validate_new_canonical_destination(root, relative_path)
        os.link(temporary_name, target)
        return target
    except FileExistsError as exc:
        raise SnapshotTargetError("target Vault canonical destination is occupied") from exc
    except OSError as exc:
        raise SnapshotTargetError("target Vault canonical destination could not be written") from exc
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def verify_canonical_file(root: Path, relative_path: str, expected: bytes) -> Path:
    """Verify one canonical regular file still contains the exact expected bytes."""
    target = _assert_safe_destination(root, relative_path)
    try:
        node = target.lstat()
    except OSError as exc:
        raise SnapshotTargetError("Vault canonical lesson is unavailable") from exc
    if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
        raise SnapshotTargetError("Vault canonical lesson is unsafe")
    if _read_bounded_regular_file(target, node, "Vault Markdown") != expected:
        raise SnapshotPlanStaleError("canonical lesson changed after preview")
    return target


def delete_canonical_file(root: Path, relative_path: str, expected: bytes) -> None:
    """Delete one exact, previously verified canonical source lesson."""
    target = verify_canonical_file(root, relative_path, expected)
    try:
        target.unlink()
    except OSError as exc:
        raise SnapshotTargetError("source Vault canonical lesson could not be deleted") from exc


def _atomic_write(path: Path, data: bytes, *, managed_root: Path | None = None, relative_path: str | None = None) -> None:
    if managed_root is not None:
        if relative_path is None:
            raise ValueError("a managed write needs a relative path")
        path = _assert_safe_destination(managed_root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if managed_root is not None and relative_path is not None:
        # mkdir and temporary-file creation are mutation boundaries too.  Check
        # again immediately before replacing the destination; this is a narrow
        # best-effort TOCTOU defence, not a claim of filesystem transactionality.
        path = _assert_safe_destination(managed_root, relative_path)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if managed_root is not None and relative_path is not None:
            path = _assert_safe_destination(managed_root, relative_path)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _atomic_write_scoped(path: Path, data: bytes, label: str) -> None:
    """Atomically update a scoped document after every path component is safe."""
    path = prepare_scoped_mutation_path(path, label)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_safe_scoped_path(path, label, create_parents=True)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _assert_restore_scoped_boundaries(context: ActiveVaultContext) -> None:
    """Reject substituted data/cache scope parents before canonical mutation."""
    _assert_safe_scoped_path(context.candidates_path, "candidate state")
    _assert_safe_scoped_path(context.projection_path, "lesson projection")
    _assert_safe_scoped_path(context.topic_model_path, "topic model")


def _restore_apply(validated: ValidatedSnapshot, context: ActiveVaultContext, decisions: DuplicateDecisionStore) -> None:
    current = read_canonical_markdown_files(context.vault_dir)
    with zipfile.ZipFile(io.BytesIO(validated.raw)) as archive:
        incoming = {item.path: archive.read(f"{CANONICAL_PREFIX}{item.path}") for item in validated.canonical}
    changed = {path for path in set(current) | set(incoming) if current.get(path) != incoming.get(path)}
    for rel in changed:
        _assert_safe_destination(context.vault_dir, rel)
    candidates_before = _read_regular_state_file(context.candidates_path, "candidate state")
    decisions_before = decisions.export_scope(context.duplicate_decision_scope)
    try:
        for rel in sorted(set(current) - set(incoming)):
            _assert_safe_destination(context.vault_dir, rel).unlink()
        for rel in sorted(incoming):
            if current.get(rel) != incoming[rel]:
                _atomic_write(
                    context.vault_dir / rel,
                    incoming[rel],
                    managed_root=context.vault_dir,
                    relative_path=rel,
                )
        _atomic_write_scoped(context.candidates_path, validated.candidates, "candidate state")
        decisions.replace_scope(context.duplicate_decision_scope, list(validated.duplicate_decisions))
    except Exception as exc:
        rollback_succeeded = True
        try:
            for rel in sorted(set(incoming) - set(current)):
                target = _assert_safe_destination(context.vault_dir, rel)
                if target.exists():
                    target.unlink()
            for rel, content in current.items():
                _atomic_write(
                    context.vault_dir / rel,
                    content,
                    managed_root=context.vault_dir,
                    relative_path=rel,
                )
            if candidates_before is None:
                path = _assert_safe_scoped_path(context.candidates_path, "candidate state")
                path.unlink(missing_ok=True)
            else:
                _atomic_write_scoped(context.candidates_path, candidates_before, "candidate state")
            decisions.replace_scope(context.duplicate_decision_scope, decisions_before)
        except Exception:
            rollback_succeeded = False
        raise SnapshotRestoreError("snapshot canonical restore failed", rollback_succeeded=rollback_succeeded) from exc


def execute_restore(
    validated: ValidatedSnapshot,
    context: ActiveVaultContext,
    decisions: DuplicateDecisionStore,
    *,
    plan_digest: str,
    reconcile_derived: Callable[..., None],
    resolve_current_target: Callable[[], ActiveVaultContext] | None = None,
) -> RestoreResult:
    """Apply exact managed state then independently reconcile derived state."""
    if resolve_current_target is not None:
        context = resolve_current_target()
    current_preview = preview_restore(validated, context, decisions)
    if plan_digest != current_preview.plan_digest:
        raise SnapshotPlanStaleError("snapshot or target state changed after preview")
    if resolve_current_target is not None:
        checked = resolve_current_target()
        if checked != context:
            raise SnapshotPlanStaleError("selected Vault changed after preview")
        context = checked
    _assert_restore_scoped_boundaries(context)
    _restore_apply(validated, context, decisions)
    try:
        # New composition receives the exact context which passed both the
        # stale-plan check and final resolver check.  The no-argument fallback
        # keeps the domain API compatible with existing callers that have no
        # derived state to reconcile.
        try:
            inspect.signature(reconcile_derived).bind(context)
        except TypeError:
            reconcile_derived()
        else:
            reconcile_derived(context)
    except Exception:
        # The API must distinguish this recoverable partial success without
        # exposing backend exception details to an uploaded-artifact client.
        return RestoreResult(True, None, False, "Derived reconciliation failed; run a maintained refresh.", current_preview)
    return RestoreResult(True, None, True, None, current_preview)
