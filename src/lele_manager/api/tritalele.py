"""Versioned HTTP boundary for the TritaLeLe candidate workflow."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import math
from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from lele_manager.adapters.canonical_markdown_vault import (
    FilesystemCanonicalMarkdownVault,
)
from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.adapters.vault_jsonl_refresh import VaultJsonlRefresh
from lele_manager.application.candidate_approval import (
    ApprovalCandidatePersistenceError,
    ApprovalCollisionError,
    ApprovalIdentityCollisionError,
    ApprovalPathCollisionError,
    ApprovalRefreshError,
    ApprovalResult,
    ApprovalVaultStorageError,
    CandidateApprovalError,
    CandidateApprovalNotFoundError,
    CandidateApprovalService,
    InvalidApprovalInputError,
    InvalidApprovalLifecycleError,
    InvalidApprovalMetadataError,
    PartialApprovalError,
    PartialRefreshError,
    StaleApprovalRevisionError,
)
from lele_manager.application.candidate_review import (
    CandidateReviewConflictError,
    CandidateReviewError,
    CandidateReviewFilter,
    CandidateReviewService,
    CandidateReviewStorageError,
    InvalidCandidateReviewInputError,
    InvalidCandidateTransitionError,
    ReviewCandidateNotFoundError,
    StaleCandidateRevisionError,
)
from lele_manager.application.lesson_candidate import (
    CandidateRepository,
    CandidateState,
    LessonCandidate,
)
from lele_manager.application.raw_source import RawSource, SourceKind
from lele_manager.application.raw_source_chunking import (
    ChunkingSettings,
    DeterministicRawSourceChunker,
)
from lele_manager.application.raw_source_ingestion import (
    IngestionConflictError,
    IngestionPlanError,
    IngestionStagingError,
    PartialIngestionError,
    RawSourceIngestionError,
    RawSourceIngestionResult,
    RawSourceIngestionService,
)
from lele_manager.core.paths import candidates_path, lessons_path
from lele_manager.core.vault import resolve_vault_dir


router = APIRouter(prefix="/api/v1/tritalele", tags=["tritalele"])


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RawSourceRequest(_StrictRequest):
    content: str
    source_kind: SourceKind
    logical_name: str
    max_characters: int = Field(default=2_000, strict=True)


class CanonicalMetadataRequest(_StrictRequest):
    topic: str = Field(min_length=1)
    source: str = Field(min_length=1)
    importance: int = Field(ge=1, le=5, strict=True)
    tags: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    date: str = Field(min_length=1)
    title: str = Field(min_length=1)


class CandidateRevisionRequest(_StrictRequest):
    expected_revision: int = Field(ge=0, strict=True)
    proposed_text: str | None = Field(default=None, min_length=1)
    proposed_metadata: CanonicalMetadataRequest | None = None
    reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_proposal(self) -> CandidateRevisionRequest:
        if self.proposed_text is None and self.proposed_metadata is None:
            raise ValueError("proposed_text or proposed_metadata is required")
        return self


class CandidateTransitionRequest(_StrictRequest):
    expected_revision: int = Field(ge=0, strict=True)
    reason: str | None = Field(default=None, min_length=1)


class CandidateApprovalRequest(_StrictRequest):
    expected_revision: int = Field(ge=0, strict=True)


class SourceSpanResponse(BaseModel):
    start: int
    end: int


class CandidateProvenanceResponse(BaseModel):
    source_kind: str
    source_logical_name: str
    source_fingerprint: str
    ingested_at: str
    chunk_index: int | None
    source_span: SourceSpanResponse | None
    run_metadata: dict[str, Any]
    transformations: list[dict[str, Any]]


class CandidateReviewEventResponse(BaseModel):
    revision: int
    action: str
    occurred_at: str
    previous_state: str
    resulting_state: str
    reason: str | None


class CandidateResponse(BaseModel):
    candidate_id: str
    state: str
    revision: int
    original_text: str
    proposed_text: str | None
    effective_text: str
    proposed_metadata: dict[str, Any] | None
    provenance: CandidateProvenanceResponse
    review_history: list[CandidateReviewEventResponse]


class CandidateListResponse(BaseModel):
    count: int
    candidates: list[CandidateResponse]


class IngestionSourceResponse(BaseModel):
    kind: str
    logical_name: str
    fingerprint: str


class IngestionChunkingResponse(BaseModel):
    max_characters: int


class IngestionCountsResponse(BaseModel):
    planned: int
    created: int
    skipped: int
    pending: int


class IngestionResultResponse(BaseModel):
    preview: bool
    source: IngestionSourceResponse
    chunking: IngestionChunkingResponse
    candidate_ids: list[str]
    created_candidate_ids: list[str]
    skipped_candidate_ids: list[str]
    pending_candidate_ids: list[str]
    counts: IngestionCountsResponse
    candidates: list[CandidateResponse]


class RefreshOutcomeResponse(BaseModel):
    refreshed: bool


class ApprovalResultResponse(BaseModel):
    candidate_id: str
    candidate_revision: int
    lesson_id: str
    relative_vault_path: str
    vault_write_outcome: str
    candidate_state_changed: bool
    refresh_outcome: RefreshOutcomeResponse


class APIErrorDetail(BaseModel):
    code: str
    message: str
    recovery: dict[str, Any] | None = None


class APIErrorResponse(BaseModel):
    detail: APIErrorDetail


_ERROR_DESCRIPTIONS = {
    400: "The request is structurally valid but violates the workflow input contract.",
    404: "The requested candidate does not exist.",
    409: "The operation conflicts with candidate state, revision, or canonical identity.",
    500: "The ingestion plan violated an application invariant.",
    503: "A configured workflow storage operation is unavailable or partially completed.",
}


def _error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {
        status: {"model": APIErrorResponse, "description": _ERROR_DESCRIPTIONS[status]}
        for status in statuses
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _raise_api_error(
    status_code: int,
    code: str,
    message: str,
    recovery: dict[str, Any] | None = None,
) -> NoReturn:
    detail: dict[str, Any] = {"code": code, "message": message}
    if recovery is not None:
        detail["recovery"] = recovery
    raise HTTPException(status_code=status_code, detail=detail) from None


def get_candidate_repository() -> CandidateRepository:
    """Build a fresh repository for the configured local staging document."""
    try:
        path = candidates_path()
    except (OSError, RuntimeError):
        _raise_api_error(
            503,
            "candidate_storage_unavailable",
            "Candidate staging storage is unavailable.",
        )
    return JsonCandidateRepository(path)


def get_ingestion_service(
    repository: Annotated[CandidateRepository, Depends(get_candidate_repository)],
) -> RawSourceIngestionService:
    return RawSourceIngestionService(
        DeterministicRawSourceChunker(), repository, _utc_now
    )


def get_review_service(
    repository: Annotated[CandidateRepository, Depends(get_candidate_repository)],
) -> CandidateReviewService:
    return CandidateReviewService(repository, _utc_now)


def get_approval_service(
    repository: Annotated[CandidateRepository, Depends(get_candidate_repository)],
) -> CandidateApprovalService:
    try:
        vault_dir = resolve_vault_dir()
        projection_path = lessons_path()
    except (OSError, RuntimeError):
        _raise_api_error(
            503,
            "approval_storage_unavailable",
            "Canonical approval storage is unavailable.",
        )
    return CandidateApprovalService(
        repository,
        FilesystemCanonicalMarkdownVault(vault_dir),
        VaultJsonlRefresh(vault_dir, projection_path),
        _utc_now,
    )


def _json_value(value: object) -> Any:
    """Copy immutable domain JSON values into transport-native containers."""
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise TypeError("response contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        if not all(type(key) is str for key in value):
            raise TypeError("response mapping keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError("response contains a non-JSON value")


def _candidate_response(candidate: LessonCandidate) -> CandidateResponse:
    provenance = candidate.provenance
    span = provenance.source_span
    proposed_metadata = _json_value(candidate.proposed_metadata)
    run_metadata = _json_value(provenance.run_metadata)
    transformations = _json_value(provenance.transformations)
    assert proposed_metadata is None or isinstance(proposed_metadata, dict)
    assert isinstance(run_metadata, dict)
    assert isinstance(transformations, list)
    return CandidateResponse(
        candidate_id=candidate.candidate_id,
        state=candidate.state.value,
        revision=candidate.revision,
        original_text=candidate.text,
        proposed_text=candidate.proposed_text,
        effective_text=candidate.effective_text,
        proposed_metadata=proposed_metadata,
        provenance=CandidateProvenanceResponse(
            source_kind=provenance.source_kind.value,
            source_logical_name=provenance.source_logical_name,
            source_fingerprint=provenance.source_fingerprint,
            ingested_at=provenance.ingested_at.isoformat(),
            chunk_index=provenance.chunk_index,
            source_span=(
                None if span is None else SourceSpanResponse(start=span.start, end=span.end)
            ),
            run_metadata=run_metadata,
            transformations=transformations,
        ),
        review_history=[
            CandidateReviewEventResponse(
                revision=event.revision,
                action=event.action.value,
                occurred_at=event.occurred_at.isoformat(),
                previous_state=event.previous_state.value,
                resulting_state=event.resulting_state.value,
                reason=event.reason,
            )
            for event in candidate.review_history
        ],
    )


def _ingestion_response(
    result: RawSourceIngestionResult,
    source: RawSource,
    settings: ChunkingSettings,
) -> IngestionResultResponse:
    return IngestionResultResponse(
        preview=result.preview,
        source=IngestionSourceResponse(
            kind=source.kind.value,
            logical_name=source.logical_name,
            fingerprint=result.source_fingerprint,
        ),
        chunking=IngestionChunkingResponse(max_characters=settings.max_characters),
        candidate_ids=list(result.candidate_ids),
        created_candidate_ids=list(result.created_candidate_ids),
        skipped_candidate_ids=list(result.skipped_candidate_ids),
        pending_candidate_ids=list(result.pending_candidate_ids),
        counts=IngestionCountsResponse(
            planned=len(result.planned_candidates),
            created=result.created_count,
            skipped=result.skipped_count,
            pending=result.pending_count,
        ),
        candidates=[_candidate_response(item) for item in result.planned_candidates],
    )


def _approval_response(result: ApprovalResult) -> ApprovalResultResponse:
    return ApprovalResultResponse(
        candidate_id=result.candidate_id,
        candidate_revision=result.candidate_revision,
        lesson_id=result.lesson_id,
        relative_vault_path=result.relative_vault_path,
        vault_write_outcome=result.vault_write_outcome.value,
        candidate_state_changed=result.candidate_state_changed,
        refresh_outcome=RefreshOutcomeResponse(
            refreshed=result.refresh_outcome.refreshed
        ),
    )


def _raise_ingestion_error(error: RawSourceIngestionError) -> NoReturn:
    if isinstance(error, PartialIngestionError):
        _raise_api_error(
            503,
            "partial_ingestion",
            "Candidate staging stopped after a partial ingestion.",
            {
                "created_candidate_ids": list(error.created_candidate_ids),
                "failed_candidate_id": error.failed_candidate_id,
                "remaining_candidate_ids": list(error.remaining_candidate_ids),
            },
        )
    if isinstance(error, IngestionConflictError):
        recovery: dict[str, Any] = {}
        if error.candidate_id is not None:
            recovery["candidate_id"] = error.candidate_id
        if error.created_candidate_ids:
            recovery["created_candidate_ids"] = list(error.created_candidate_ids)
        _raise_api_error(
            409,
            "ingestion_conflict",
            "Candidate identity conflicts with staged content.",
            recovery or None,
        )
    if isinstance(error, IngestionPlanError):
        _raise_api_error(
            500,
            "invalid_ingestion_plan",
            "The ingestion plan failed an application invariant.",
        )
    if isinstance(error, IngestionStagingError):
        recovery = {}
        if error.failed_candidate_id is not None:
            recovery["failed_candidate_id"] = error.failed_candidate_id
        if error.remaining_candidate_ids:
            recovery["remaining_candidate_ids"] = list(error.remaining_candidate_ids)
        _raise_api_error(
            503,
            "candidate_storage_unavailable",
            "Candidate staging storage is unavailable.",
            recovery or None,
        )
    _raise_api_error(
        503,
        "ingestion_unavailable",
        "Raw-source ingestion is unavailable.",
    )


def _raise_review_error(error: CandidateReviewError) -> NoReturn:
    if isinstance(error, ReviewCandidateNotFoundError):
        _raise_api_error(404, "candidate_not_found", "Candidate was not found.")
    if isinstance(error, StaleCandidateRevisionError):
        _raise_api_error(
            409,
            "stale_candidate_revision",
            "Candidate revision is stale.",
        )
    if isinstance(error, InvalidCandidateTransitionError):
        _raise_api_error(
            409,
            "invalid_candidate_transition",
            "Candidate transition is not allowed.",
        )
    if isinstance(error, CandidateReviewConflictError):
        _raise_api_error(
            409,
            "candidate_review_conflict",
            "Candidate staging contains a conflicting identity.",
        )
    if isinstance(error, InvalidCandidateReviewInputError):
        _raise_api_error(
            400,
            "invalid_candidate_review_input",
            "Candidate review input is invalid.",
        )
    if isinstance(error, CandidateReviewStorageError):
        _raise_api_error(
            503,
            "candidate_storage_unavailable",
            "Candidate staging storage is unavailable.",
        )
    _raise_api_error(
        503,
        "candidate_review_unavailable",
        "Candidate review is unavailable.",
    )


def _raise_approval_error(error: CandidateApprovalError) -> NoReturn:
    if isinstance(error, PartialApprovalError):
        _raise_api_error(
            503,
            "partial_approval",
            "The canonical lesson exists, but candidate persistence may be unknown.",
            {
                "candidate_id": error.candidate_id,
                "lesson_id": error.lesson_id,
                "relative_vault_path": error.relative_vault_path,
                "vault_write_outcome": error.vault_write_outcome.value,
                "candidate_persistence_state": "unknown",
            },
        )
    if isinstance(error, PartialRefreshError):
        partial = _approval_response(error.partial_result)
        _raise_api_error(
            503,
            "partial_refresh",
            (
                "The canonical lesson and candidate approval succeeded, but the "
                "derived projection refresh failed."
            ),
            {
                "partial_approval_result": partial.model_dump(mode="json"),
                "canonical_lesson_persisted": True,
                "candidate_approval_persisted": True,
                "projection_refreshed": False,
            },
        )
    if isinstance(error, CandidateApprovalNotFoundError):
        _raise_api_error(404, "candidate_not_found", "Candidate was not found.")
    if isinstance(error, StaleApprovalRevisionError):
        _raise_api_error(
            409,
            "stale_approval_revision",
            "Candidate approval revision is stale.",
        )
    if isinstance(error, InvalidApprovalLifecycleError):
        _raise_api_error(
            409,
            "invalid_approval_lifecycle",
            "Candidate is not in an approvable state.",
        )
    if isinstance(error, ApprovalPathCollisionError):
        _raise_api_error(
            409,
            "approval_path_collision",
            "Canonical lesson path is already occupied.",
        )
    if isinstance(error, ApprovalIdentityCollisionError):
        _raise_api_error(
            409,
            "approval_identity_collision",
            "Canonical lesson identity already exists at another path.",
        )
    if isinstance(error, ApprovalCollisionError):
        _raise_api_error(
            409,
            "approval_collision",
            "Canonical lesson publication conflicts with existing content.",
        )
    if isinstance(error, InvalidApprovalMetadataError):
        _raise_api_error(
            400,
            "invalid_approval_metadata",
            "Candidate approval metadata is invalid.",
        )
    if isinstance(error, InvalidApprovalInputError):
        _raise_api_error(
            400,
            "invalid_approval_input",
            "Candidate approval input is invalid.",
        )
    if isinstance(error, ApprovalVaultStorageError):
        _raise_api_error(
            503,
            "vault_storage_unavailable",
            "Canonical vault storage is unavailable.",
        )
    if isinstance(error, ApprovalCandidatePersistenceError):
        _raise_api_error(
            503,
            "candidate_approval_persistence_unavailable",
            "Candidate approval persistence is unavailable.",
        )
    if isinstance(error, ApprovalRefreshError):
        _raise_api_error(
            503,
            "derived_refresh_unavailable",
            "Derived lesson projection refresh is unavailable.",
        )
    _raise_api_error(
        503,
        "candidate_approval_unavailable",
        "Candidate approval is unavailable.",
    )


def _run_ingestion(
    body: RawSourceRequest,
    service: RawSourceIngestionService,
    *,
    preview: bool,
) -> IngestionResultResponse:
    try:
        source = RawSource(body.content, body.source_kind, body.logical_name)
    except (TypeError, ValueError, UnicodeError):
        _raise_api_error(
            400,
            "invalid_raw_source",
            "Raw source input is invalid.",
        )
    try:
        settings = ChunkingSettings(max_characters=body.max_characters)
    except (TypeError, ValueError):
        _raise_api_error(
            400,
            "invalid_chunking_settings",
            "Chunking settings are invalid.",
        )
    try:
        result = service.ingest(source, settings, preview=preview)
    except RawSourceIngestionError as error:
        _raise_ingestion_error(error)
    return _ingestion_response(result, source, settings)


@router.post(
    "/ingestion/preview",
    response_model=IngestionResultResponse,
    responses=_error_responses(400, 409, 500, 503),
    summary="Preview raw-source ingestion",
    description="Plan deterministic candidates without mutating staging, vault, or projection storage.",
    operation_id="tritalele_preview_ingestion",
)
def preview_ingestion(
    body: RawSourceRequest,
    service: Annotated[RawSourceIngestionService, Depends(get_ingestion_service)],
) -> IngestionResultResponse:
    return _run_ingestion(body, service, preview=True)


@router.post(
    "/ingestion/stage",
    response_model=IngestionResultResponse,
    responses=_error_responses(400, 409, 500, 503),
    summary="Stage raw-source candidates",
    description="Create only missing deterministic candidates in local staging.",
    operation_id="tritalele_stage_ingestion",
)
def stage_ingestion(
    body: RawSourceRequest,
    service: Annotated[RawSourceIngestionService, Depends(get_ingestion_service)],
) -> IngestionResultResponse:
    return _run_ingestion(body, service, preview=False)


@router.get(
    "/candidates",
    response_model=CandidateListResponse,
    responses=_error_responses(400, 409, 503),
    summary="List staged candidates",
    description="List candidates in deterministic order with optional review filters.",
    operation_id="tritalele_list_candidates",
)
def list_candidates(
    service: Annotated[CandidateReviewService, Depends(get_review_service)],
    state: Annotated[CandidateState | None, Query()] = None,
    source_kind: Annotated[SourceKind | None, Query()] = None,
    source_fingerprint: Annotated[str | None, Query(min_length=1)] = None,
    source_logical_name: Annotated[str | None, Query(min_length=1)] = None,
    chunk_index: Annotated[int | None, Query(ge=0)] = None,
) -> CandidateListResponse:
    try:
        filters = CandidateReviewFilter(
            state=state,
            source_kind=source_kind,
            source_fingerprint=source_fingerprint,
            source_logical_name=source_logical_name,
            chunk_index=chunk_index,
        )
        candidates = service.list_candidates(filters)
    except CandidateReviewError as error:
        _raise_review_error(error)
    return CandidateListResponse(
        count=len(candidates),
        candidates=[_candidate_response(item) for item in candidates],
    )


@router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateResponse,
    responses=_error_responses(400, 404, 409, 503),
    summary="Get one candidate",
    description="Return the stable review representation of one staged candidate.",
    operation_id="tritalele_get_candidate",
)
def get_candidate(
    candidate_id: str,
    service: Annotated[CandidateReviewService, Depends(get_review_service)],
) -> CandidateResponse:
    try:
        candidate = service.get_candidate(candidate_id)
    except CandidateReviewError as error:
        _raise_review_error(error)
    return _candidate_response(candidate)


@router.patch(
    "/candidates/{candidate_id}",
    response_model=CandidateResponse,
    responses=_error_responses(400, 404, 409, 503),
    summary="Revise one candidate",
    description="Revise proposed text or complete canonical metadata using optimistic concurrency.",
    operation_id="tritalele_revise_candidate",
)
def revise_candidate(
    candidate_id: str,
    body: CandidateRevisionRequest,
    service: Annotated[CandidateReviewService, Depends(get_review_service)],
) -> CandidateResponse:
    try:
        current = service.get_candidate(candidate_id)
        proposed_text = (
            current.proposed_text
            if body.proposed_text is None
            else body.proposed_text
        )
        proposed_metadata: Mapping[str, object] | None = (
            current.proposed_metadata
            if body.proposed_metadata is None
            else body.proposed_metadata.model_dump()
        )
        revised = service.revise_candidate(
            candidate_id,
            expected_revision=body.expected_revision,
            proposed_text=proposed_text,
            proposed_metadata=proposed_metadata,
            reason=body.reason,
        )
    except CandidateReviewError as error:
        _raise_review_error(error)
    return _candidate_response(revised)


@router.post(
    "/candidates/{candidate_id}/accept",
    response_model=CandidateResponse,
    responses=_error_responses(400, 404, 409, 503),
    summary="Accept one candidate",
    description="Move one staged candidate into review using its expected revision.",
    operation_id="tritalele_accept_candidate",
)
def accept_candidate(
    candidate_id: str,
    body: CandidateTransitionRequest,
    service: Annotated[CandidateReviewService, Depends(get_review_service)],
) -> CandidateResponse:
    try:
        accepted = service.accept_candidate(
            candidate_id,
            expected_revision=body.expected_revision,
            reason=body.reason,
        )
    except CandidateReviewError as error:
        _raise_review_error(error)
    return _candidate_response(accepted)


@router.post(
    "/candidates/{candidate_id}/reject",
    response_model=CandidateResponse,
    responses=_error_responses(400, 404, 409, 503),
    summary="Reject one candidate",
    description="Reject one staged or in-review candidate using its expected revision.",
    operation_id="tritalele_reject_candidate",
)
def reject_candidate(
    candidate_id: str,
    body: CandidateTransitionRequest,
    service: Annotated[CandidateReviewService, Depends(get_review_service)],
) -> CandidateResponse:
    try:
        rejected = service.reject_candidate(
            candidate_id,
            expected_revision=body.expected_revision,
            reason=body.reason,
        )
    except CandidateReviewError as error:
        _raise_review_error(error)
    return _candidate_response(rejected)


@router.post(
    "/candidates/{candidate_id}/approve",
    response_model=ApprovalResultResponse,
    responses=_error_responses(400, 404, 409, 503),
    summary="Approve one candidate",
    description="Publish one accepted candidate and refresh the derived lesson projection.",
    operation_id="tritalele_approve_candidate",
)
def approve_candidate(
    candidate_id: str,
    body: CandidateApprovalRequest,
    service: Annotated[CandidateApprovalService, Depends(get_approval_service)],
) -> ApprovalResultResponse:
    try:
        result = service.approve(
            candidate_id, expected_revision=body.expected_revision
        )
    except CandidateApprovalError as error:
        _raise_approval_error(error)
    return _approval_response(result)
