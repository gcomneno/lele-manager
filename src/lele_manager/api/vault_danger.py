"""HTTP boundary for explicit per-Vault destructive operations."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from lele_manager.core.duplicate_decisions import (
    DuplicateDecisionStore,
    DuplicateDecisionStoreError,
)
from lele_manager.core.paths import (
    DEFAULT_DUPLICATE_DECISIONS_FILENAME,
    data_dir,
    resolved_data_dir,
)
from lele_manager.core.vault import import_vault_to_jsonl
from lele_manager.core.vault_danger import (
    VaultDangerBackupError,
    VaultDangerConfirmationError,
    VaultDangerError,
    VaultDangerMergeVerificationError,
    VaultDangerPlanStaleError,
    VaultDangerPreview,
    VaultDangerResult,
    VaultDangerTargetError,
    execute_vault_danger,
    persist_snapshot_backup,
    preview_vault_danger,
)
from lele_manager.core.vault_registry import (
    ActiveVaultContext,
    VaultConflictError,
    VaultNotFoundError,
    VaultPathError,
    VaultRegistryError,
    VaultRegistryStore,
)
from lele_manager.core.vault_snapshot import (
    SnapshotTargetError,
    SnapshotValidationError,
    create_snapshot,
    invalidate_scoped_derived_artifact,
    prepare_scoped_mutation_path,
)


router = APIRouter(prefix="/vault-danger", tags=["vault-danger"])


class VaultDangerPreviewRequest(BaseModel):
    vault_id: str = Field(min_length=1, max_length=64)
    operation: Literal["empty", "reset", "delete", "merge_delete_source"]
    destination_vault_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_destination(self) -> "VaultDangerPreviewRequest":
        if self.operation == "merge_delete_source":
            if self.destination_vault_id is None:
                raise ValueError("merge_delete_source requires destination_vault_id")
            if self.destination_vault_id == self.vault_id:
                raise ValueError("source and destination Vaults must differ")
        elif self.destination_vault_id is not None:
            raise ValueError("destination_vault_id is valid only for merge_delete_source")
        return self


class VaultDangerExecuteRequest(VaultDangerPreviewRequest):
    plan_digest: str = Field(min_length=64, max_length=64)
    confirmation: str = Field(min_length=1, max_length=1024)
    backup_before: bool = False


class VaultDangerPreviewResponse(BaseModel):
    plan_digest: str
    operation: str
    vault_id: str
    vault_name: str
    vault_path: str
    active: bool
    approved_count: int
    filesystem_entry_count: int
    candidate_state_present: bool
    duplicate_decision_count: int
    confirmation_text: str
    deletes: list[str]
    keeps: list[str]
    destination_vault_id: str | None = None
    destination_name: str | None = None
    destination_path: str | None = None
    merge_verified: bool


class VaultDangerResultResponse(BaseModel):
    preview: VaultDangerPreviewResponse
    backup_path: str | None = None
    canonical_deleted: int
    canonical_complete: bool
    canonical_error: str | None = None
    editorial_cleared: bool | None = None
    editorial_error: str | None = None
    derived_cleared: bool | None = None
    derived_error: str | None = None
    vault_directory_deleted: bool | None = None
    registry_removed: bool | None = None
    registry_error: str | None = None
    partial: bool


def _preview_response(preview: VaultDangerPreview) -> VaultDangerPreviewResponse:
    return VaultDangerPreviewResponse(
        plan_digest=preview.plan_digest,
        operation=preview.operation,
        vault_id=preview.vault_id,
        vault_name=preview.vault_name,
        vault_path=preview.vault_path,
        active=preview.active,
        approved_count=preview.approved_count,
        filesystem_entry_count=preview.filesystem_entry_count,
        candidate_state_present=preview.candidate_state_present,
        duplicate_decision_count=preview.duplicate_decision_count,
        confirmation_text=preview.confirmation_text,
        deletes=list(preview.deletes),
        keeps=list(preview.keeps),
        destination_vault_id=preview.destination_vault_id,
        destination_name=preview.destination_name,
        destination_path=preview.destination_path,
        merge_verified=preview.merge_verified,
    )


def _result_response(result: VaultDangerResult) -> VaultDangerResultResponse:
    return VaultDangerResultResponse(
        preview=_preview_response(result.preview),
        backup_path=result.backup_path,
        canonical_deleted=result.canonical_deleted,
        canonical_complete=result.canonical_complete,
        canonical_error=result.canonical_error,
        editorial_cleared=result.editorial_cleared,
        editorial_error=result.editorial_error,
        derived_cleared=result.derived_cleared,
        derived_error=result.derived_error,
        vault_directory_deleted=result.vault_directory_deleted,
        registry_removed=result.registry_removed,
        registry_error=result.registry_error,
        partial=result.partial,
    )


def _store() -> VaultRegistryStore:
    return VaultRegistryStore()


def _context(vault_id: str) -> ActiveVaultContext:
    try:
        return _store().safe_context_for_registered(vault_id)
    except VaultRegistryError as exc:
        raise _http_error(exc) from exc


def _active_id() -> str:
    try:
        return _store().active().id
    except VaultRegistryError as exc:
        raise _http_error(exc) from exc


def _destination(body: VaultDangerPreviewRequest) -> ActiveVaultContext | None:
    if body.destination_vault_id is None:
        return None
    return _context(body.destination_vault_id)


def _decisions() -> DuplicateDecisionStore:
    # Preview stays side-effect free: resolving the data root must not mkdir.
    return DuplicateDecisionStore(
        resolved_data_dir() / DEFAULT_DUPLICATE_DECISIONS_FILENAME
    )


def _invalidate_cache(request: Request, context: ActiveVaultContext) -> None:
    lock = getattr(request.app.state, "sim_index_lock", None)
    if lock is None:
        return
    with lock:
        key = getattr(request.app.state, "sim_index_key", None)
        if key is not None and key[0] == context.vault_id:
            request.app.state.sim_index = None
            request.app.state.sim_index_key = None


def _reconcile(request: Request, context: ActiveVaultContext) -> None:
    invalidate_scoped_derived_artifact(context.topic_model_path, "topic model")
    prepare_scoped_mutation_path(context.projection_path, "lesson projection")
    import_vault_to_jsonl(context.vault_dir, context.projection_path)
    _invalidate_cache(request, context)


def _backup(context: ActiveVaultContext, decisions: DuplicateDecisionStore) -> str:
    try:
        artifact = create_snapshot(context, decisions)
    except (SnapshotValidationError, SnapshotTargetError, DuplicateDecisionStoreError) as exc:
        raise VaultDangerBackupError(
            "requested backup failed; destructive operation was not started"
        ) from exc
    return persist_snapshot_backup(
        artifact,
        backup_root=data_dir() / "backups",
        vault_id=context.vault_id,
    )


def _remove_registry(context: ActiveVaultContext) -> None:
    try:
        _store().remove(context.vault_id)
    except VaultRegistryError as exc:
        raise VaultDangerError(str(exc)) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, VaultNotFoundError):
        status = 404
    elif isinstance(
        exc,
        (
            VaultDangerPlanStaleError,
            VaultDangerConfirmationError,
            VaultDangerMergeVerificationError,
            VaultDangerTargetError,
            VaultConflictError,
            VaultPathError,
            SnapshotTargetError,
        ),
    ):
        status = 409
    elif isinstance(exc, VaultDangerBackupError):
        status = 503
    elif isinstance(exc, VaultRegistryError):
        status = 503
    else:
        status = 422
    return HTTPException(
        status_code=status,
        detail={
            "code": getattr(exc, "code", "vault_danger_invalid"),
            "message": str(exc),
        },
    )


@router.post("/preview", response_model=VaultDangerPreviewResponse)
def preview_danger(body: VaultDangerPreviewRequest) -> VaultDangerPreviewResponse:
    """Build a read-only destructive preview for one registered Vault."""
    try:
        return _preview_response(
            preview_vault_danger(
                operation=body.operation,
                target=_context(body.vault_id),
                active_vault_id=_active_id(),
                decisions=_decisions(),
                destination=_destination(body),
            )
        )
    except (VaultDangerError, SnapshotTargetError, DuplicateDecisionStoreError) as exc:
        raise _http_error(exc) from exc


@router.post("/execute", response_model=VaultDangerResultResponse)
def execute_danger(body: VaultDangerExecuteRequest, request: Request) -> VaultDangerResultResponse:
    """Execute only the exact previewed target/state and typed confirmation."""
    try:
        target = _context(body.vault_id)
        destination = _destination(body)
        decisions = _decisions()
        result = execute_vault_danger(
            operation=body.operation,
            target=target,
            active_vault_id=_active_id(),
            decisions=decisions,
            plan_digest=body.plan_digest,
            confirmation=body.confirmation,
            backup_before=body.backup_before,
            destination=destination,
            resolve_target=lambda: _context(body.vault_id),
            resolve_active_vault_id=_active_id,
            resolve_destination=(
                (lambda: _context(body.destination_vault_id or ""))
                if body.destination_vault_id is not None
                else None
            ),
            reconcile_derived=lambda context: _reconcile(request, context),
            invalidate_cache=lambda context: _invalidate_cache(request, context),
            remove_registry=_remove_registry,
            create_backup=lambda context: _backup(context, decisions),
        )
        return _result_response(result)
    except (VaultDangerError, SnapshotTargetError, DuplicateDecisionStoreError) as exc:
        raise _http_error(exc) from exc
