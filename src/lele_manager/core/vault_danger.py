"""Preview-first destructive operations for explicit registered Vaults.

The danger-zone boundary is intentionally stateless.  A preview describes one
registered Vault identity and the exact maintained state that may be destroyed;
execution recomputes that plan before the first destructive mutation.
"""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Literal

from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.core.duplicate_decisions import DuplicateDecisionStore
from lele_manager.core.json_compat import canonical_json
from lele_manager.core.vault_registry import ActiveVaultContext
from lele_manager.core.vault_snapshot import (
    SnapshotPlanStaleError,
    SnapshotTargetError,
    delete_canonical_file,
    invalidate_scoped_derived_artifact,
    read_canonical_markdown_files,
    verify_canonical_file,
)


DANGER_SEMANTICS_VERSION = 1
DangerOperation = Literal["empty", "reset", "delete", "merge_delete_source"]


class VaultDangerError(RuntimeError):
    code = "vault_danger_invalid"


class VaultDangerPlanStaleError(VaultDangerError):
    code = "vault_danger_plan_stale"


class VaultDangerConfirmationError(VaultDangerError):
    code = "vault_danger_confirmation_mismatch"


class VaultDangerBackupError(VaultDangerError):
    code = "vault_danger_backup_failed"


class VaultDangerTargetError(VaultDangerError):
    code = "vault_danger_target_unsafe"


class VaultDangerMergeVerificationError(VaultDangerError):
    code = "vault_danger_merge_unverified"


@dataclass(frozen=True)
class VaultDangerPreview:
    plan_digest: str
    operation: DangerOperation
    vault_id: str
    vault_name: str
    vault_path: str
    active: bool
    approved_count: int
    filesystem_entry_count: int
    candidate_state_present: bool
    duplicate_decision_count: int
    confirmation_text: str
    deletes: tuple[str, ...]
    keeps: tuple[str, ...]
    destination_vault_id: str | None = None
    destination_name: str | None = None
    destination_path: str | None = None
    merge_verified: bool = False


@dataclass(frozen=True)
class VaultDangerResult:
    preview: VaultDangerPreview
    backup_path: str | None
    canonical_deleted: int
    canonical_complete: bool
    canonical_error: str | None
    editorial_cleared: bool | None
    editorial_error: str | None
    derived_cleared: bool | None
    derived_error: str | None
    vault_directory_deleted: bool | None
    vault_directory_error: str | None
    registry_removed: bool | None
    registry_error: str | None

    @property
    def partial(self) -> bool:
        return any(
            value is False
            for value in (
                self.canonical_complete,
                self.editorial_cleared,
                self.derived_cleared,
                self.vault_directory_deleted,
                self.registry_removed,
            )
            if value is not None
        )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_safe_scoped_state(path: Path, label: str) -> Path:
    """Validate one fixed root/vaults/id/file path without creating state."""
    try:
        root = path.parents[2]
    except IndexError as exc:
        raise VaultDangerTargetError(f"{label} managed path is malformed") from exc
    try:
        root_node = root.lstat()
    except FileNotFoundError:
        return path
    except OSError as exc:
        raise VaultDangerTargetError(f"{label} could not be safely inspected") from exc
    if stat.S_ISLNK(root_node.st_mode) or not stat.S_ISDIR(root_node.st_mode):
        raise VaultDangerTargetError(f"{label} managed root is unsafe")
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current = current / part
        try:
            node = current.lstat()
        except FileNotFoundError:
            return path
        except OSError as exc:
            raise VaultDangerTargetError(f"{label} could not be safely inspected") from exc
        if stat.S_ISLNK(node.st_mode) or not stat.S_ISDIR(node.st_mode):
            raise VaultDangerTargetError(f"{label} managed directory is unsafe")
    try:
        node = path.lstat()
    except FileNotFoundError:
        return path
    except OSError as exc:
        raise VaultDangerTargetError(f"{label} could not be safely inspected") from exc
    if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
        raise VaultDangerTargetError(f"{label} is unsafe")
    return path


def _read_scoped_state_file(path: Path, label: str) -> bytes | None:
    path = _assert_safe_scoped_state(path, label)
    try:
        node = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise VaultDangerTargetError(f"{label} could not be safely inspected") from exc
    if node.st_size > 32 * 1024 * 1024:
        raise VaultDangerTargetError(f"{label} exceeds size limits")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise VaultDangerTargetError(f"{label} could not be safely read") from exc


def _context_value(context: ActiveVaultContext) -> dict[str, str]:
    return {
        "id": context.vault_id,
        "name": context.display_name,
        "vault": str(context.vault_dir),
        "projection": str(context.projection_path),
        "candidates": str(context.candidates_path),
        "model": str(context.topic_model_path),
        "decision_scope": context.duplicate_decision_scope,
    }


def _canonical_state(files: dict[str, bytes]) -> list[dict[str, str]]:
    return [
        {"path": path, "sha256": _sha(data)}
        for path, data in sorted(files.items())
    ]


def _confirmation(operation: DangerOperation, name: str) -> str:
    verb = "EMPTY" if operation == "empty" else "RESET" if operation == "reset" else "DELETE"
    return f"{verb} {name}"


def _scan_managed_tree(root: Path) -> tuple[str, ...]:
    """Describe a Vault tree that contains only directories and Markdown files.

    Delete-from-disk deliberately refuses to delete unrelated regular files,
    symlinks, sockets, devices or other filesystem nodes.  That keeps the
    destructive boundary aligned with the canonical namespace LeLe Manager owns.
    """
    try:
        root_node = root.lstat()
    except OSError as exc:
        raise VaultDangerTargetError("registered Vault directory is unavailable") from exc
    if stat.S_ISLNK(root_node.st_mode) or not stat.S_ISDIR(root_node.st_mode):
        raise VaultDangerTargetError("registered Vault directory is unavailable or unsafe")

    entries: list[str] = []

    def visit(directory: Path, relative: PurePosixPath) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise VaultDangerTargetError("Vault directory could not be safely inspected") from exc
        for child in children:
            rel = relative / child.name
            try:
                node = child.lstat()
            except OSError as exc:
                raise VaultDangerTargetError("Vault entry could not be safely inspected") from exc
            if stat.S_ISLNK(node.st_mode):
                raise VaultDangerTargetError("Vault contains a symlinked entry")
            if stat.S_ISDIR(node.st_mode):
                entries.append(f"dir:{rel.as_posix()}")
                visit(child, rel)
                continue
            if stat.S_ISREG(node.st_mode) and child.suffix.lower() == ".md":
                entries.append(f"file:{rel.as_posix()}")
                continue
            if stat.S_ISREG(node.st_mode):
                raise VaultDangerTargetError(
                    "Vault contains a non-Markdown file that LeLe Manager will not delete"
                )
            raise VaultDangerTargetError("Vault contains an unsupported special filesystem entry")

    visit(root, PurePosixPath())
    return tuple(sorted(entries))


def _lesson_ids(files: dict[str, bytes]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for relative_path, raw in files.items():
        try:
            frontmatter, _body = parse_markdown_with_frontmatter(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, TypeError) as exc:
            raise VaultDangerMergeVerificationError(
                "canonical Markdown could not be read while verifying the merged destination"
            ) from exc
        actual_id = frontmatter.get("id")
        if actual_id is None:
            lesson_id = relative_path[:-3]
        elif isinstance(actual_id, str) and actual_id.strip():
            lesson_id = actual_id.strip()
        else:
            raise VaultDangerMergeVerificationError(
                "canonical lesson has an invalid stable ID"
            )
        if lesson_id in result:
            raise VaultDangerMergeVerificationError(
                "canonical lesson stable ID is ambiguous"
            )
        result[lesson_id] = raw
    return result


def _verify_merged_source(source: dict[str, bytes], destination: dict[str, bytes]) -> None:
    source_ids = _lesson_ids(source)
    destination_ids = _lesson_ids(destination)
    missing = [
        lesson_id
        for lesson_id, raw in sorted(source_ids.items())
        if destination_ids.get(lesson_id) != raw
    ]
    if missing:
        raise VaultDangerMergeVerificationError(
            "source Vault is not fully represented by exact stable-ID/canonical-byte matches in destination"
        )


def _plan_digest(
    *,
    operation: DangerOperation,
    target: ActiveVaultContext,
    active_vault_id: str,
    canonical: dict[str, bytes],
    tree_entries: tuple[str, ...],
    candidate_state: bytes | None,
    decisions: list[dict[str, str]],
    destination: ActiveVaultContext | None,
    destination_canonical: dict[str, bytes] | None,
) -> str:
    value: dict[str, object] = {
        "danger_semantics_version": DANGER_SEMANTICS_VERSION,
        "operation": operation,
        "target": _context_value(target),
        "active_vault_id": active_vault_id,
        "canonical": _canonical_state(canonical),
        "tree": list(tree_entries),
    }
    if operation in ("reset", "delete", "merge_delete_source"):
        value["candidate_sha256"] = _sha(candidate_state) if candidate_state is not None else None
        value["duplicate_decisions"] = decisions
    if destination is not None and destination_canonical is not None:
        value["destination"] = _context_value(destination)
        value["destination_canonical"] = _canonical_state(destination_canonical)
    return _sha((canonical_json(value) + "\n").encode("utf-8"))


def preview_vault_danger(
    *,
    operation: DangerOperation,
    target: ActiveVaultContext,
    active_vault_id: str,
    decisions: DuplicateDecisionStore,
    destination: ActiveVaultContext | None = None,
) -> VaultDangerPreview:
    if operation not in ("empty", "reset", "delete", "merge_delete_source"):
        raise VaultDangerError("unsupported danger-zone operation")
    if operation == "merge_delete_source" and destination is None:
        raise VaultDangerError("merge-and-delete requires an explicit destination Vault")
    if operation != "merge_delete_source" and destination is not None:
        raise VaultDangerError("destination Vault is valid only for merge-and-delete")
    if destination is not None and destination.vault_id == target.vault_id:
        raise VaultDangerError("source and destination Vaults must be distinct")
    if operation in ("delete", "merge_delete_source") and target.vault_id == active_vault_id:
        raise VaultDangerTargetError("activate another Vault before deleting this Vault from disk")

    canonical = read_canonical_markdown_files(target.vault_dir)
    tree_entries: tuple[str, ...] = ()
    if operation in ("delete", "merge_delete_source"):
        tree_entries = _scan_managed_tree(target.vault_dir)

    candidate_state = (
        _read_scoped_state_file(target.candidates_path, "candidate state")
        if operation in ("reset", "delete", "merge_delete_source")
        else None
    )
    decision_entries = (
        decisions.export_scope(target.duplicate_decision_scope)
        if operation in ("reset", "delete", "merge_delete_source")
        else []
    )

    destination_canonical: dict[str, bytes] | None = None
    merge_verified = False
    if destination is not None:
        destination_canonical = read_canonical_markdown_files(destination.vault_dir)
        _verify_merged_source(canonical, destination_canonical)
        merge_verified = True

    if operation == "empty":
        deletes = ("all approved canonical Markdown lessons", "target Vault derived projection/model refreshed")
        keeps = ("Vault registration", "Vault directory", "candidate staging", "duplicate decisions")
    elif operation == "reset":
        deletes = (
            "all approved canonical Markdown lessons",
            "candidate staging",
            "Vault-scoped duplicate decisions",
            "Vault-scoped projection/model state",
        )
        keeps = ("Vault registration", "Vault directory", "global application configuration")
    else:
        deletes = (
            "the managed Vault directory after proving it contains only canonical Markdown",
            "candidate staging",
            "Vault-scoped duplicate decisions",
            "Vault-scoped projection/model state",
            "Vault registry entry",
        )
        keeps = ("other registered Vaults", "global application configuration")

    plan_digest = _plan_digest(
        operation=operation,
        target=target,
        active_vault_id=active_vault_id,
        canonical=canonical,
        tree_entries=tree_entries,
        candidate_state=candidate_state,
        decisions=decision_entries,
        destination=destination,
        destination_canonical=destination_canonical,
    )
    return VaultDangerPreview(
        plan_digest=plan_digest,
        operation=operation,
        vault_id=target.vault_id,
        vault_name=target.display_name,
        vault_path=str(target.vault_dir),
        active=target.vault_id == active_vault_id,
        approved_count=len(canonical),
        filesystem_entry_count=len(tree_entries),
        candidate_state_present=candidate_state is not None,
        duplicate_decision_count=len(decision_entries),
        confirmation_text=_confirmation(operation, target.display_name),
        deletes=deletes,
        keeps=keeps,
        destination_vault_id=destination.vault_id if destination is not None else None,
        destination_name=destination.display_name if destination is not None else None,
        destination_path=str(destination.vault_dir) if destination is not None else None,
        merge_verified=merge_verified,
    )


def persist_snapshot_backup(
    artifact: bytes,
    *,
    backup_root: Path,
    vault_id: str,
) -> str:
    """Persist one already-created snapshot atomically before destruction."""
    try:
        backup_root.mkdir(parents=True, exist_ok=True)
        node = backup_root.lstat()
    except OSError as exc:
        raise VaultDangerBackupError("backup directory could not be prepared") from exc
    if stat.S_ISLNK(node.st_mode) or not stat.S_ISDIR(node.st_mode):
        raise VaultDangerBackupError("backup directory is unsafe")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"lele-vault-{vault_id}-{timestamp}-{uuid.uuid4().hex[:8]}.snapshot.zip"
    destination = backup_root / filename
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=backup_root, prefix=".vault-backup.", delete=False) as handle:
            handle.write(artifact)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        if backup_root.is_symlink():
            raise VaultDangerBackupError("backup directory changed while writing")
        os.replace(temporary_name, destination)
    except (OSError, VaultDangerBackupError) as exc:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        if isinstance(exc, VaultDangerBackupError):
            raise
        raise VaultDangerBackupError("backup artifact could not be saved") from exc
    return str(destination)


def _verify_all_canonical(root: Path, canonical: dict[str, bytes]) -> None:
    for relative_path, expected in sorted(canonical.items()):
        verify_canonical_file(root, relative_path, expected)


def _delete_canonical_set(root: Path, canonical: dict[str, bytes]) -> tuple[int, str | None]:
    try:
        _verify_all_canonical(root, canonical)
    except (SnapshotPlanStaleError, SnapshotTargetError) as exc:
        raise VaultDangerPlanStaleError(
            "canonical state changed after destructive preflight"
        ) from exc
    deleted = 0
    for relative_path, expected in sorted(canonical.items()):
        try:
            delete_canonical_file(root, relative_path, expected)
        except (SnapshotPlanStaleError, SnapshotTargetError) as exc:
            return deleted, str(exc)
        deleted += 1
    return deleted, None


def _remove_empty_directories(root: Path, tree_entries: tuple[str, ...]) -> None:
    directories = [entry[4:] for entry in tree_entries if entry.startswith("dir:")]
    for relative_path in sorted(directories, key=lambda value: (value.count("/"), value), reverse=True):
        try:
            (root / PurePosixPath(relative_path)).rmdir()
        except OSError as exc:
            raise VaultDangerTargetError("Vault directory changed while deleting from disk") from exc
    try:
        root.rmdir()
    except OSError as exc:
        raise VaultDangerTargetError("Vault directory could not be removed") from exc


def _clear_editorial(context: ActiveVaultContext, decisions: DuplicateDecisionStore) -> tuple[bool, str | None]:
    errors: list[str] = []
    try:
        invalidate_scoped_derived_artifact(context.candidates_path, "candidate state")
    except SnapshotTargetError as exc:
        errors.append(str(exc))
    try:
        decisions.replace_scope(context.duplicate_decision_scope, [])
    except Exception as exc:
        errors.append(str(exc))
    return not errors, "; ".join(errors) or None


def _clear_derived(
    context: ActiveVaultContext,
    *,
    invalidate_cache: Callable[[ActiveVaultContext], None],
) -> tuple[bool, str | None]:
    errors: list[str] = []
    for path, label in (
        (context.projection_path, "lesson projection"),
        (context.topic_model_path, "topic model"),
    ):
        try:
            invalidate_scoped_derived_artifact(path, label)
        except SnapshotTargetError as exc:
            errors.append(str(exc))
    try:
        invalidate_cache(context)
    except Exception as exc:
        errors.append(str(exc))
    return not errors, "; ".join(errors) or None


def execute_vault_danger(
    *,
    operation: DangerOperation,
    target: ActiveVaultContext,
    active_vault_id: str,
    decisions: DuplicateDecisionStore,
    plan_digest: str,
    confirmation: str,
    backup_before: bool,
    resolve_target: Callable[[], ActiveVaultContext],
    resolve_active_vault_id: Callable[[], str],
    reconcile_derived: Callable[[ActiveVaultContext], None],
    invalidate_cache: Callable[[ActiveVaultContext], None],
    remove_registry: Callable[[ActiveVaultContext], None],
    create_backup: Callable[[ActiveVaultContext], str],
    destination: ActiveVaultContext | None = None,
    resolve_destination: Callable[[], ActiveVaultContext] | None = None,
) -> VaultDangerResult:
    """Re-prove the preview and then execute the explicit destructive operation."""
    current = preview_vault_danger(
        operation=operation,
        target=target,
        active_vault_id=active_vault_id,
        decisions=decisions,
        destination=destination,
    )
    if current.plan_digest != plan_digest:
        raise VaultDangerPlanStaleError("danger-zone target or managed state changed after preview")
    if confirmation != current.confirmation_text:
        raise VaultDangerConfirmationError("typed confirmation does not match the current Vault")

    final_target = resolve_target()
    final_active_id = resolve_active_vault_id()
    final_destination = resolve_destination() if resolve_destination is not None else None
    if final_target != target or final_active_id != active_vault_id or final_destination != destination:
        raise VaultDangerPlanStaleError("registered Vault context changed after preview")

    final_preview = preview_vault_danger(
        operation=operation,
        target=final_target,
        active_vault_id=final_active_id,
        decisions=decisions,
        destination=final_destination,
    )
    if final_preview.plan_digest != current.plan_digest:
        raise VaultDangerPlanStaleError("danger-zone state changed during execution preflight")

    backup_path: str | None = None
    if backup_before:
        try:
            backup_path = create_backup(final_target)
        except Exception as exc:
            if isinstance(exc, VaultDangerBackupError):
                raise
            raise VaultDangerBackupError("requested backup failed; destructive operation was not started") from exc

    canonical = read_canonical_markdown_files(final_target.vault_dir)
    canonical_deleted, canonical_error = _delete_canonical_set(final_target.vault_dir, canonical)
    canonical_complete = canonical_error is None and canonical_deleted == len(canonical)

    editorial_cleared: bool | None = None
    editorial_error: str | None = None
    derived_cleared: bool | None = None
    derived_error: str | None = None
    directory_deleted: bool | None = None
    directory_error: str | None = None
    registry_removed: bool | None = None
    registry_error: str | None = None

    if operation == "empty":
        if canonical_deleted or canonical_complete:
            try:
                reconcile_derived(final_target)
                derived_cleared = True
            except Exception as exc:
                derived_cleared = False
                derived_error = str(exc)
        return VaultDangerResult(
            final_preview,
            backup_path,
            canonical_deleted,
            canonical_complete,
            canonical_error,
            None,
            None,
            derived_cleared,
            derived_error,
            None,
            None,
            None,
            None,
        )

    if operation == "reset":
        if canonical_complete:
            editorial_cleared, editorial_error = _clear_editorial(final_target, decisions)
            derived_cleared, derived_error = _clear_derived(
                final_target,
                invalidate_cache=invalidate_cache,
            )
        elif canonical_deleted:
            try:
                reconcile_derived(final_target)
                derived_cleared = True
            except Exception as exc:
                derived_cleared = False
                derived_error = str(exc)
        return VaultDangerResult(
            final_preview,
            backup_path,
            canonical_deleted,
            canonical_complete,
            canonical_error,
            editorial_cleared,
            editorial_error,
            derived_cleared,
            derived_error,
            None,
            None,
            None,
            None,
        )

    tree_entries = _scan_managed_tree(final_target.vault_dir)
    if canonical_complete:
        try:
            _remove_empty_directories(final_target.vault_dir, tree_entries)
            directory_deleted = True
        except VaultDangerTargetError as exc:
            directory_deleted = False
            directory_error = str(exc)
    else:
        directory_deleted = False

    if directory_deleted:
        editorial_cleared, editorial_error = _clear_editorial(final_target, decisions)
        derived_cleared, derived_error = _clear_derived(
            final_target,
            invalidate_cache=invalidate_cache,
        )
        try:
            remove_registry(final_target)
            registry_removed = True
        except Exception as exc:
            registry_removed = False
            registry_error = str(exc)
    elif canonical_deleted:
        try:
            reconcile_derived(final_target)
            derived_cleared = True
        except Exception as exc:
            derived_cleared = False
            derived_error = str(exc)

    return VaultDangerResult(
        final_preview,
        backup_path,
        canonical_deleted,
        canonical_complete,
        canonical_error,
        editorial_cleared,
        editorial_error,
        derived_cleared,
        derived_error,
        directory_deleted,
        directory_error,
        registry_removed,
        registry_error,
    )
