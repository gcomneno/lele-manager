from __future__ import annotations

import uuid
import platform
import pandas as pd

from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any, Callable, List, Literal, Mapping, Optional, cast
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from pathlib import Path
from datetime import datetime, timezone
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from threading import Lock

from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.lesson_candidate import (
    CandidateRepositoryError,
    CandidateState,
)
from lele_manager.core.paths import duplicate_decisions_path
from lele_manager.core.duplicate_decisions import (
    DuplicateDecisionStore,
    DuplicateDecisionStoreError,
    material_fingerprint,
)
from lele_manager.application.lesson_writing import (
    CanonicalLessonWriteAmbiguousError,
    CanonicalLessonWriteNotFoundError,
    CanonicalLessonWriteStorageError,
    write_canonical_lesson_source,
)
from lele_manager.core.runtime_transparency import (
    RuntimePathDescription,
    describe_runtime_paths,
)
from lele_manager.core.analytics import compute_metadata_options, compute_stats_summary, compute_timeline
from lele_manager.application.dataframes import records_to_legacy_dataframe
from lele_manager.application.external_lessons import external_lessons_feed
from lele_manager.application.lesson_deletion import (
    CanonicalLessonDeletionResult,
    LessonDeletionNotFoundError,
    LessonDeletionResult,
    LessonDeletionStorageError,
    PartialLessonDeletionRefreshError,
    delete_canonical_lesson_source,
    delete_canonical_lesson,
)
from lele_manager.composition import legacy_jsonl_append_facade, projection_store
from lele_manager.core.lifecycle import LifecycleState, normalize_lifecycle
from lele_manager.core.projection_store import (
    DuplicateLessonIdError,
    LessonOrder,
    LessonQuery,
    ProjectionStoreError,
)
from lele_manager.core.deduplication import DEFAULT_MIN_SCORE, find_duplicates
from lele_manager.core.doctor import DoctorOperationalError, check_markdown_files
from lele_manager.core.export import search_results_to_markdown
from lele_manager.core.vault import (
    build_vault_tree,
    find_markdown_by_id,
    find_markdown_paths_by_id,
    import_vault_to_jsonl,
    resolve_vault_dir,
    default_relative_path,
    write_lesson_markdown,
)
from lele_manager.core.vault_registry import (
    ActiveVaultContext,
    VaultConflictError,
    VaultNotFoundError,
    VaultPathError,
    VaultRegistryError,
    VaultRegistryStore,
    active_vault_context,
)
from lele_manager.core.vault_snapshot import (
    RestorePreview,
    SnapshotPlanStaleError,
    SnapshotRestoreError,
    SnapshotTargetError,
    SnapshotValidationError,
    MAX_ARTIFACT_SIZE,
    create_snapshot,
    execute_restore,
    invalidate_scoped_derived_artifact,
    prepare_scoped_mutation_path,
    preview_restore,
    validate_snapshot,
)
from lele_manager.core.vault_transfer import (
    TransferPreview,
    TransferResult,
    VaultTransferConflictError,
    VaultTransferError,
    VaultTransferPlanStaleError,
    execute_transfer,
    list_transferable_lessons,
    preview_transfer,
)
from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.ml.similarity import LessonSimilarityIndex
from lele_manager.ml.topic_model import (
    load_topic_model,
    save_topic_model,
    train_topic_model,
)
from lele_manager.ml.similarity_service import similar_by_text, similar_by_lesson_id
from lele_manager.api.tritalele import router as tritalele_router


# Override espliciti (usati nei test via monkeypatch) — se None si usa default_*_path()
DATA_PATH: Path | None = None
MODEL_PATH: Path | None = None
DUPLICATE_DECISIONS_PATH: Path | None = None


def get_data_path() -> Path:
    return DATA_PATH if DATA_PATH is not None else active_vault_context().projection_path


def get_model_path() -> Path:
    return MODEL_PATH if MODEL_PATH is not None else active_vault_context().topic_model_path


def get_active_vault_context() -> ActiveVaultContext:
    """One immutable context for operations crossing canonical and derived state."""
    # Module-level path overrides are an intentionally narrow test seam. They
    # never come from production configuration and therefore cannot become a
    # second persisted active-Vault authority.
    if DATA_PATH is not None or MODEL_PATH is not None:
        vault = resolve_vault_dir()
        projection = DATA_PATH if DATA_PATH is not None else vault / ".lele-test-lessons.jsonl"
        model = MODEL_PATH if MODEL_PATH is not None else vault / ".lele-test-topic-model.joblib"
        return ActiveVaultContext("test-override", vault.name or "Vault", vault, projection, projection.parent / "candidates.json", model, "test-override")
    try:
        return active_vault_context()
    except VaultRegistryError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc


def get_duplicate_decisions_path() -> Path:
    return (
        DUPLICATE_DECISIONS_PATH
        if DUPLICATE_DECISIONS_PATH is not None
        else duplicate_decisions_path()
    )


def resolve_gui_dir() -> Path | None:
    """Return GUI static directory if a production build is present."""
    api_dir = Path(__file__).resolve().parent
    candidates = [
        api_dir.parent / "gui" / "static",
        api_dir.parents[2] / "frontend" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


GUI_DIR: Path | None = resolve_gui_dir()


try:
    __version__ = version("lele-manager")
except PackageNotFoundError:
    __version__ = "0.0.0"


app = FastAPI(
    title="LeLe Manager API",
    description="API per gestire e cercare le Lesson Learned (LeLe).",
    version=__version__,
)
app.include_router(tritalele_router)


# -----------------------------------------------------------------------------
# Schemi Pydantic
# -----------------------------------------------------------------------------
class LessonBase(BaseModel):
    text: str = Field(..., description="Testo della lesson learned")
    topic: Optional[str] = Field(
        None, description="Topic/macrocategoria (es. python, cpp, linux)"
    )
    source: Optional[str] = Field(
        None, description="Origine: chatgpt, libro, esperimento, note, ..."
    )
    importance: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Importanza (1-5).",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Lista di tag liberi.",
    )
    date: Optional[str] = Field(
        default=None,
        description="Data in formato libero (es. 2025-11-28).",
    )
    title: Optional[str] = Field(
        default=None,
        description="Titolo opzionale della LeLe.",
    )
    created_at: Optional[str] = Field(
        default=None,
        description="Timestamp tecnico (ISO 8601 UTC). Se omesso viene generato dal server.",
    )
    lifecycle: LifecycleState = Field(
        default="active",
        description="Stato lifecycle canonico della LeLe.",
    )
    superseded_by: Optional[str] = Field(
        default=None,
        description="Stable ID della LeLe che sostituisce questa LeLe.",
    )


class LessonCreate(LessonBase):
    id: Optional[str] = Field(
        default=None,
        description="ID opzionale. Se non fornito, viene generato un UUID.",
    )


class Lesson(LessonBase):
    id: str


class LessonSearchResult(Lesson):
    pass


class ExternalLessonResponse(BaseModel):
    id: str
    text: str
    title: Optional[str]
    topic: Optional[str]
    source: Optional[str]
    importance: Optional[int]
    tags: List[str]
    date: Optional[str]
    created_at: Optional[str]


class ExternalLessonsResponse(BaseModel):
    schema_version: Literal[1]
    generation: str
    total_lessons: int
    returned_lessons: int
    lessons: List[ExternalLessonResponse]


class LessonSearchRequest(BaseModel):
    """Payload per la ricerca avanzata POST /lessons/search."""

    q: Optional[str] = Field(
        default=None,
        description="Substring case-insensitive cercata nel campo 'text'.",
    )
    topic_in: Optional[List[str]] = Field(
        default=None,
        description="Lista di topic ammessi (OR logico).",
    )
    source_in: Optional[List[str]] = Field(
        default=None,
        description="Lista di source ammessi (OR logico).",
    )
    importance_gte: Optional[int] = Field(
        default=None,
        description="Filtro: importance >= questo valore.",
    )
    importance_lte: Optional[int] = Field(
        default=None,
        description="Filtro: importance <= questo valore.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Numero massimo di risultati da restituire.",
    )


class ExportSearchRequest(LessonSearchRequest):
    """Payload per POST /export/search — stessi filtri di /lessons/search."""

    include_frontmatter: bool = Field(
        default=True,
        description="Se true, ogni LeLe include frontmatter YAML (Obsidian-ready).",
    )
    ids_in: Optional[List[str]] = Field(
        default=None,
        description="Opzionale: limita l'export a questi ID (dopo gli altri filtri).",
    )


class ExportSearchResponse(BaseModel):
    markdown: str
    n_lessons: int


class SimilarMeta(BaseModel):
    data_mtime_ns: int
    model_mtime_ns: int
    top_k: int
    min_score: float
    query_topic: Optional[str] = None
    query_tags: Optional[List[str]] = None


class SimilarItem(BaseModel):
    id: str
    score: float
    text_preview: str
    rank: Optional[int] = None
    topic: Optional[str] = None
    tags_shared: Optional[List[str]] = None


class SimilarResponse(BaseModel):
    query: str
    results: List[SimilarItem]
    meta: Optional[SimilarMeta] = None


class SimilarTextRequest(BaseModel):
    text: str = Field(..., description="Testo libero da confrontare.")
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SimilarBatchItemRequest(BaseModel):
    text: str = Field(..., description="Testo libero da confrontare.")
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SimilarBatchRequest(BaseModel):
    items: List[SimilarBatchItemRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Batch di richieste di similarità.",
    )


class SimilarBatchResponse(BaseModel):
    items: List[SimilarResponse]


class DuplicateLessonSnapshot(Lesson):
    """Read-only lesson data captured from the same snapshot as a duplicate pair."""

    path: Optional[str] = None


class DuplicatePairResponse(BaseModel):
    left_id: str
    right_id: str
    left_position: int
    right_position: int
    left_path: Optional[str] = None
    right_path: Optional[str] = None
    kind: Literal["exact", "near"]
    score: float
    reasons: List[str]
    shared_tags: List[str]
    left_fingerprint: str
    right_fingerprint: str
    resolution_available: bool
    resolution_problem: Optional[str] = None
    left_lesson: DuplicateLessonSnapshot
    right_lesson: DuplicateLessonSnapshot


class DuplicateReportResponse(BaseModel):
    lessons_analyzed: int
    total_pairs: int
    exact_pairs: int
    near_pairs: int
    min_score: float
    exact_only: bool
    suppressed_pairs: int = 0
    pairs: List[DuplicatePairResponse]


class DuplicateNotDuplicatesRequest(BaseModel):
    left_id: str = Field(min_length=1)
    right_id: str = Field(min_length=1)
    left_fingerprint: str = Field(min_length=1)
    right_fingerprint: str = Field(min_length=1)


class DuplicateDecisionResponse(BaseModel):
    left_id: str
    right_id: str
    left_fingerprint: str
    right_fingerprint: str
    decided_at: str


class DuplicateMergeRefreshOutcomeResponse(BaseModel):
    attempted: bool
    refreshed: bool


class DuplicateMergeRequest(BaseModel):
    survivor_id: str = Field(min_length=1)
    superseded_id: str = Field(min_length=1)
    expected_survivor_fingerprint: str = Field(min_length=1)
    expected_superseded_fingerprint: str = Field(min_length=1)
    result: "LessonVaultWrite"

    @model_validator(mode="after")
    def validate_distinct_ids(self) -> "DuplicateMergeRequest":
        if self.survivor_id == self.superseded_id:
            raise ValueError("survivor_id and superseded_id must be distinct")
        return self


class DuplicateMergeResponse(BaseModel):
    completed: bool
    survivor_id: str
    survivor_written: bool
    superseded_id: str
    superseded_deleted: bool
    refresh_outcome: DuplicateMergeRefreshOutcomeResponse
    failure: Optional[dict[str, str]] = None


class TrainResponse(BaseModel):
    message: str
    n_lessons: int
    topics: List[str]


class HealthResponse(BaseModel):
    status: str
    has_data: bool
    has_model: bool


class RuntimeInfoResponse(BaseModel):
    version: str


class RuntimePathProvenanceResponse(BaseModel):
    kind: Literal[
        "configuration_override",
        "legacy_override",
        "platform_default",
        "product_default",
        "runtime_override",
        "managed_registry",
    ]
    variable: Optional[str] = None
    deprecated: bool = False


class RuntimePathResponse(BaseModel):
    key: str
    path: str
    role: Literal[
        "authoritative_user_data",
        "persistent_application_state",
        "derived_rebuildable_artifact",
        "cache_temporary_state",
    ]
    exists: bool
    kind: Literal["directory", "file"]
    provenance: RuntimePathProvenanceResponse


class SettingsRuntimeResponse(BaseModel):
    version: str
    health: HealthResponse
    paths: List[RuntimePathResponse]


class AboutLinkResponse(BaseModel):
    label: str
    url: str


class AboutResponse(BaseModel):
    product_name: str
    version: str
    tagline: str
    attribution: str
    license_id: str
    license_summary: str
    license_url: str
    local_first_statement: str
    repository_url: str
    issue_tracker_url: str
    releases_url: str
    changelog_url: str
    documentation_url: str
    python_version: str
    platform_system: str
    platform_release: str


class DiagnosticsPreviewResponse(BaseModel):
    product_name: str
    version: str
    python_version: str
    platform_system: str
    platform_release: str
    health: HealthResponse
    paths: List[RuntimePathResponse]


class VaultStatusResponse(BaseModel):
    vault_dir: str
    exists: bool
    vault_id: str | None = None
    display_name: str | None = None


class VaultRegistryItemResponse(BaseModel):
    id: str
    name: str
    path: str
    active: bool
    available: bool
    lesson_count: int | None = None


class VaultRegistryMutation(BaseModel):
    name: str = Field(min_length=1)
    path: str | None = None


class VaultRestorePreviewResponse(BaseModel):
    plan_digest: str
    target_vault_id: str
    target_name: str
    target_path: str
    source_vault_id: str
    source_vault_name: str
    canonical_file_count: int
    additions: List[str]
    replacements: List[str]
    removals: List[str]
    unchanged: List[str]
    editorial_state: List[str]
    derived_effects: List[str]


class VaultRestoreResponse(BaseModel):
    canonical_restored: bool
    rollback_succeeded: bool | None = None
    derived_reconciled: bool
    derived_error: str | None = None
    preview: VaultRestorePreviewResponse


class VaultTransferSelection(BaseModel):
    lesson_id: str = Field(min_length=1, max_length=512)
    resolution: Literal["transfer", "keep_destination", "skip"] | None = None


class VaultTransferRequest(BaseModel):
    source_vault_id: str = Field(min_length=1, max_length=64)
    destination_vault_id: str = Field(min_length=1, max_length=64)
    operation: Literal["merge", "copy", "move"]
    selections: List[VaultTransferSelection] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_selection(self) -> "VaultTransferRequest":
        if self.source_vault_id == self.destination_vault_id:
            raise ValueError("source_vault_id and destination_vault_id must differ")
        if any(not item.lesson_id.strip() for item in self.selections):
            raise ValueError("selection lesson IDs must not be blank")
        if len({item.lesson_id for item in self.selections}) != len(self.selections):
            raise ValueError("selection lesson IDs must be unique")
        return self


class VaultTransferExecuteRequest(VaultTransferRequest):
    plan_digest: str = Field(min_length=64, max_length=64)


class VaultTransferItemPreviewResponse(BaseModel):
    lesson_id: str
    source_path: str
    source_sha256: str
    destination_path: str
    destination_sha256: str | None = None
    classification: Literal["new", "identical", "already_present", "same_id", "path_conflict", "likely_duplicate"]
    resolution: Literal["transfer", "keep_destination", "skip"] | None = None
    duplicate_lesson_ids: List[str]


class VaultTransferPreviewResponse(BaseModel):
    plan_digest: str
    operation: str
    source_vault_id: str
    source_name: str
    source_path: str
    destination_vault_id: str
    destination_name: str
    destination_path: str
    items: List[VaultTransferItemPreviewResponse]


class VaultTransferItemResultResponse(BaseModel):
    lesson_id: str
    source_path: str
    destination_path: str
    outcome: str
    destination_canonical: str
    destination_derived: str
    source_canonical: str
    source_derived: str


class VaultTransferResponse(BaseModel):
    preview: VaultTransferPreviewResponse
    items: List[VaultTransferItemResultResponse]
    destination_derived_reconciled: bool | None = None
    destination_derived_error: str | None = None
    source_derived_reconciled: bool | None = None
    source_derived_error: str | None = None


class VaultTransferSourceLessonResponse(BaseModel):
    lesson_id: str
    source_path: str


class DashboardCandidateSummary(BaseModel):
    total: int
    staged: int
    in_review: int
    rejected: int
    approved: int


class DashboardSummaryResponse(BaseModel):
    health_status: str
    vault_exists: bool
    vault_markdown_files: Optional[int] = None
    projection_exists: bool
    model_exists: bool
    stats: Optional["StatsSummaryResponse"] = None
    candidates: Optional[DashboardCandidateSummary] = None


class VaultTreeResponse(BaseModel):
    vault_dir: str
    tree: dict


class VaultImportResponse(BaseModel):
    message: str
    n_lessons: int
    output_path: str
    topics: List[str]


class VaultDoctorProblemResponse(BaseModel):
    code: str
    message: str
    path: str
    field: Optional[str] = None
    severity: Literal["error"]


class VaultDoctorReportResponse(BaseModel):
    valid: bool
    files_checked: int
    checked_files: List[str]
    unique_ids: int
    error_count: int
    problems: List[VaultDoctorProblemResponse]


class LessonVaultWrite(BaseModel):
    """Payload per scrittura LeLe nel vault Markdown."""

    text: str = Field(..., description="Corpo markdown (senza frontmatter).")
    topic: str = Field(..., min_length=1)
    source: str = Field(default="note")
    importance: int = Field(default=3, ge=1, le=5)
    tags: Optional[List[str]] = Field(default=None)
    date: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)


class LessonVaultCreate(LessonVaultWrite):
    id: Optional[str] = Field(
        default=None,
        description="ID LeLe. Se omesso viene derivato da topic/data/titolo.",
    )


class RefreshOutcomeResponse(BaseModel):
    refreshed: bool


class LessonDeleteResponse(BaseModel):
    lesson_id: str
    relative_vault_path: str
    canonical_deleted: Literal[True]
    refresh_outcome: RefreshOutcomeResponse


class BulkLessonDeleteRequest(BaseModel):
    """Explicit, bounded IDs from the current Browse result snapshot."""

    lesson_ids: List[str] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_lesson_ids(self) -> "BulkLessonDeleteRequest":
        if any(not lesson_id.strip() for lesson_id in self.lesson_ids):
            raise ValueError("lesson_ids must not contain blank IDs")
        if len(set(self.lesson_ids)) != len(self.lesson_ids):
            raise ValueError("lesson_ids must not contain duplicate IDs")
        return self


class BulkLessonDeleteDeletedItem(BaseModel):
    lesson_id: str
    relative_vault_path: str


class BulkLessonDeleteFailedItem(BaseModel):
    lesson_id: str
    code: Literal["not_found", "storage_error"]


class BulkRefreshOutcomeResponse(BaseModel):
    attempted: bool
    refreshed: bool


class BulkLessonDeleteResponse(BaseModel):
    requested_count: int
    deleted: List[BulkLessonDeleteDeletedItem]
    failed: List[BulkLessonDeleteFailedItem]
    refresh_outcome: BulkRefreshOutcomeResponse


class OpsRefreshResponse(BaseModel):
    import_result: VaultImportResponse
    train_result: Optional[TrainResponse] = None


class TagCount(BaseModel):
    tag: str
    count: int


class TopicCount(BaseModel):
    topic: str
    count: int


class StatsSummaryResponse(BaseModel):
    n_lessons: int
    n_topics: int
    n_unique_tags: int
    avg_text_length: float
    avg_importance: Optional[float] = None
    top_tags: List[TagCount]
    by_topic: List[TopicCount]


class MetadataOption(BaseModel):
    value: str
    count: int


class EditorMetadataOptionsResponse(BaseModel):
    topics: List[MetadataOption]
    tags: List[MetadataOption]
    sources: List[MetadataOption]


class TimelineBucket(BaseModel):
    key: str
    count: int
    lesson_ids: List[str]


class TimelineResponse(BaseModel):
    group_by: str
    buckets: List[TimelineBucket]


# -----------------------------------------------------------------------------
# Helper di I/O
# -----------------------------------------------------------------------------
def _ensure_model_dir(model_path: Path | None = None) -> None:
    (model_path or get_model_path()).parent.mkdir(parents=True, exist_ok=True)


def load_lessons_df(context: ActiveVaultContext | None = None) -> pd.DataFrame:
    """
    Carica il JSONL delle LeLe in un DataFrame.
    Se il file non esiste, restituisce un DataFrame vuoto con colonne standard.
    Gestisce errori di parsing in modo esplicito.
    """
    data_path = context.projection_path if context is not None else get_data_path()
    try:
        records = projection_store(data_path).snapshot().list()
        df = records_to_legacy_dataframe(records)
    except ProjectionStoreError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel parsing di {data_path}: {e}",
        ) from e

    # Assicuriamoci che almeno queste colonne esistano
    for col in [
        "id",
        "text",
        "topic",
        "source",
        "importance",
        "tags",
        "date",
        "title",
        "created_at",
        "lifecycle",
        "superseded_by",
    ]:
        if col not in df.columns:
            df[col] = None

    return df


def _safe_str_series(s: pd.Series) -> pd.Series:
    """
    Convert a Series to safe strings without turning NaN/NaT into 'nan'/'NaT'.
    """
    return s.fillna("").astype(str)


def _safe_dt_series(s: pd.Series) -> pd.Series:
    """
    Parse free-form date strings to datetime; invalid/missing becomes NaT.
    """
    return pd.to_datetime(s, errors="coerce", utc=True)


def append_lesson_to_jsonl(lesson: Lesson) -> None:
    """
    Appende una singola LeLe al file JSONL.
    """
    record = lesson.dict()
    try:
        legacy_jsonl_append_facade(get_data_path()).append(record)
    except DuplicateLessonIdError as exc:
        raise HTTPException(
            status_code=409, detail=f"Lesson ID già esistente: {lesson.id}"
        ) from exc
    except ProjectionStoreError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Dataset esistente non valido; append annullato: {exc}",
        ) from exc


def _file_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def _similarity_cache_key(
    data_path: Path, model_path: Path, context: ActiveVaultContext | None = None,
) -> tuple[str, str, str, int, int]:
    # Artifact paths and stable identity prevent equal mtimes from crossing Vaults.
    context = context or get_active_vault_context()
    return (context.vault_id, str(data_path), str(model_path), _file_mtime_ns(data_path), _file_mtime_ns(model_path))


def _normalize_tags(raw: object) -> set[str]:
    if isinstance(raw, list):
        return {str(t).strip() for t in raw if str(t).strip()}
    return set()


def _parse_frontmatter_tags(text: str) -> set[str]:
    """Estrae tag dal frontmatter YAML (editor / testo con ---)."""
    import re

    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return set()
    m = re.match(r"---\s*\n(.*?)\n---", stripped, re.DOTALL)
    if not m:
        return set()
    fm = m.group(1)
    tm = re.search(r"^tags:\s*(.+)$", fm, re.MULTILINE)
    if not tm:
        return set()
    raw = tm.group(1).strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return {t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()}


def _text_preview(text: str, max_len: int = 120) -> str:
    preview = text.replace("\n", " ")
    if len(preview) > max_len:
        return preview[: max_len - 3] + "..."
    return preview


def _build_similar_items(
    df: pd.DataFrame,
    results_raw: list,
    *,
    explain: bool,
    query_tags: set[str] | None = None,
) -> List[SimilarItem]:
    df_indexed = df.set_index("id")
    text_map = df_indexed["text"].fillna("").astype(str).to_dict()
    topic_map = (
        df_indexed["topic"].fillna("").astype(str).to_dict()
        if "topic" in df_indexed.columns
        else {}
    )
    tags_series = df_indexed["tags"] if "tags" in df_indexed.columns else None

    items: List[SimilarItem] = []
    for i, r in enumerate(results_raw, start=1):
        lesson_id = str(r.lesson_id)
        topic_val: Optional[str] = None
        tags_shared: Optional[List[str]] = None
        if explain:
            raw_topic = topic_map.get(lesson_id, "")
            topic_val = raw_topic if raw_topic else None
            if query_tags and tags_series is not None:
                row_tags = _normalize_tags(tags_series.get(lesson_id))
                shared = sorted(query_tags & row_tags)
                if shared:
                    tags_shared = shared
        items.append(
            SimilarItem(
                id=lesson_id,
                score=float(r.score),
                text_preview=_text_preview(text_map.get(lesson_id, "")),
                rank=i if explain else None,
                topic=topic_val if explain else None,
                tags_shared=tags_shared if explain else None,
            )
        )
    return items


def _build_similar_meta(
    *,
    explain: bool,
    top_k: int,
    min_score: float,
    query_topic: Optional[str] = None,
    query_tags: set[str] | None = None,
    context: ActiveVaultContext | None = None,
) -> Optional[SimilarMeta]:
    if not explain:
        return None
    data_path = context.projection_path if context is not None else get_data_path()
    model_path = context.topic_model_path if context is not None else get_model_path()
    _vault_id, _data_path, _model_path, data_mtime_ns, model_mtime_ns = _similarity_cache_key(
        data_path=data_path, model_path=model_path, context=context
    )
    return SimilarMeta(
        data_mtime_ns=int(data_mtime_ns),
        model_mtime_ns=int(model_mtime_ns),
        top_k=top_k,
        min_score=min_score,
        query_topic=query_topic or None,
        query_tags=sorted(query_tags) if query_tags else None,
    )


def invalidate_similarity_cache() -> None:
    """
    Invalidate cached LessonSimilarityIndex in API layer.
    Safe to call even if cache wasn't initialized yet.
    """
    lock = getattr(app.state, "sim_index_lock", None)
    if lock is None:
        app.state.sim_index_lock = Lock()
        lock = app.state.sim_index_lock

    with lock:
        app.state.sim_index = None
        app.state.sim_index_key = None


def invalidate_similarity_cache_for_context(context: ActiveVaultContext) -> None:
    """Invalidate only a cached index belonging to one explicit Vault.

    The API currently keeps at most one index, so clearing a cached index for a
    different Vault would be needless cross-Vault derived-state mutation.
    """
    lock = getattr(app.state, "sim_index_lock", None)
    if lock is None:
        return
    with lock:
        key = getattr(app.state, "sim_index_key", None)
        if key is not None and key[0] == context.vault_id:
            app.state.sim_index = None
            app.state.sim_index_key = None


def build_similarity_index(df: pd.DataFrame, context: ActiveVaultContext | None = None):
    """
    Costruisce (o riusa) un LessonSimilarityIndex usando il topic model già allenato.
    Cached in API layer (#26).
    """
    if df.empty:
        raise HTTPException(
            status_code=400, detail="Nessuna LeLe presente nel dataset."
        )

    model_path = context.topic_model_path if context is not None else get_model_path()
    data_path = context.projection_path if context is not None else get_data_path()

    if not model_path.exists():
        raise HTTPException(
            status_code=503,
            detail="Modello di topic non disponibile. Allena prima il modello con /train/topic.",
        )

    # Lazy init cache state
    if not hasattr(app.state, "sim_index_lock"):
        app.state.sim_index_lock = Lock()
        app.state.sim_index = None
        app.state.sim_index_key = None

    key = _similarity_cache_key(data_path=data_path, model_path=model_path, context=context)

    with app.state.sim_index_lock:
        if app.state.sim_index is not None and app.state.sim_index_key == key:
            return app.state.sim_index

        pipeline = load_topic_model(str(model_path) if model_path else None)
        index = LessonSimilarityIndex.from_topic_pipeline(
            df=df, pipeline=pipeline, id_column="id"
        )

        app.state.sim_index = index
        app.state.sim_index_key = key
        return index


def _to_optional_str(value) -> Optional[str]:
    """
    Converte un valore generico in Optional[str]:

    - None o valori NA (NaN/NaT/etc.) -> None
    - altrimenti str(value)
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        # pd.isna su liste/dizionari può lanciare TypeError: in quel caso ignoriamo
        pass
    return str(value)


def _row_to_search_result(row: Mapping[Any, Any]) -> LessonSearchResult:
    """Converte una riga (dict) del DataFrame in LessonSearchResult, con la stessa
    normalizzazione usata in GET /lessons.
    """
    # id & text
    lele_id = _to_optional_str(row.get("id")) or ""
    text = _to_optional_str(row.get("text")) or ""

    # topic / source / date / title
    topic_val = _to_optional_str(row.get("topic"))
    source_val = _to_optional_str(row.get("source"))
    date_val = _to_optional_str(row.get("date"))
    title_val = _to_optional_str(row.get("title"))
    lifecycle_val = normalize_lifecycle(row.get("lifecycle"))
    superseded_by_val = _to_optional_str(row.get("superseded_by"))

    # importance: prova a convertirla, altrimenti None
    raw_importance = row.get("importance")
    if raw_importance is None or (
        isinstance(raw_importance, float) and pd.isna(raw_importance)
    ):
        importance_val: Optional[int] = None
    else:
        try:
            importance_val = int(raw_importance)
        except (TypeError, ValueError):
            importance_val = None

    # tags: solo se è una lista; converti tutto a str
    raw_tags = row.get("tags")
    tags_val: Optional[List[str]]
    if isinstance(raw_tags, list):
        tags_val = [str(t) for t in raw_tags]
    else:
        tags_val = None

    return LessonSearchResult(
        id=lele_id,
        text=text,
        topic=topic_val,
        source=source_val,
        importance=importance_val,
        tags=tags_val,
        date=date_val,
        title=title_val,
        lifecycle=lifecycle_val,
        superseded_by=superseded_by_val,
    )


def _row_to_duplicate_snapshot(row: Mapping[Any, Any]) -> DuplicateLessonSnapshot:
    """Return display data for a duplicate pair without using its (non-unique) ID."""
    lesson = _row_to_search_result(row)
    return DuplicateLessonSnapshot(
        **lesson.model_dump(exclude={"created_at"}),
        created_at=_to_optional_str(row.get("created_at")),
        path=_to_optional_str(row.get("path")),
    )


class _CanonicalDuplicateIdentityError(Exception):
    pass


def _canonical_duplicate_lesson(vault_dir: Path, lesson_id: str) -> dict:
    """Read one unambiguous canonical source for stale-write validation."""
    matches = find_markdown_paths_by_id(vault_dir, lesson_id)
    if not matches:
        raise _CanonicalDuplicateIdentityError("not_found")
    if len(matches) != 1:
        raise _CanonicalDuplicateIdentityError("ambiguous")
    try:
        frontmatter, body = parse_markdown_with_frontmatter(
            matches[0].read_text(encoding="utf-8")
        )
    except OSError as exc:
        raise _CanonicalDuplicateIdentityError("storage") from exc
    actual_id = frontmatter.get("id") or lesson_id
    if not isinstance(actual_id, str) or actual_id.strip() != lesson_id:
        raise _CanonicalDuplicateIdentityError("ambiguous")
    return {
        "id": lesson_id,
        "text": body,
        "title": frontmatter.get("title"),
        "topic": frontmatter.get("topic"),
        "source": frontmatter.get("source"),
        "importance": frontmatter.get("importance"),
        "tags": frontmatter.get("tags"),
        "date": frontmatter.get("date"),
    }


def _duplicate_pair_safety(
    left_id: str, right_id: str, vault_dir: Path | None = None,
) -> tuple[bool, str | None]:
    if not left_id or not right_id:
        return False, "Canonical identity is missing; repair the vault before resolving this pair."
    if left_id == right_id:
        return False, "Both sides have the same ID; repair duplicate canonical IDs before resolving this pair."
    if vault_dir is not None:
        if not vault_dir.is_dir():
            return False, "The configured Markdown vault is unavailable; duplicate resolution needs canonical sources."
        if len(find_markdown_paths_by_id(vault_dir, left_id)) != 1 or len(find_markdown_paths_by_id(vault_dir, right_id)) != 1:
            return False, "Canonical identity is ambiguous; repair it in Vault Doctor before resolving this pair."
    return True, None


def _duplicate_error(status: int, code: str, message: str, recovery: dict | None = None) -> HTTPException:
    detail: dict[str, object] = {"code": code, "message": message}
    if recovery is not None:
        detail["recovery"] = recovery
    return HTTPException(status_code=status, detail=detail)


# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------
@app.get("/integrations/v1/lessons", response_model=ExternalLessonsResponse)
def integration_lessons(
    q: Optional[str] = Query(default=None),
    topic: Optional[List[str]] = Query(default=None),
    source: Optional[List[str]] = Query(default=None),
    tag: Optional[List[str]] = Query(default=None),
    importance_gte: Optional[int] = Query(default=None),
    importance_lte: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, ge=1),
) -> ExternalLessonsResponse:
    """Expose a stable, read-only lesson projection to external tools."""
    query = LessonQuery(
        text=q,
        topics=topic,
        sources=source,
        tags=tag,
        importance_gte=importance_gte,
        importance_lte=importance_lte,
        order=LessonOrder.ID,
        limit=limit,
    )
    try:
        feed = external_lessons_feed(projection_store(get_data_path()), query)
    except (ProjectionStoreError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Lesson projection is unavailable.",
        ) from exc
    return ExternalLessonsResponse(
        schema_version=feed.schema_version,
        generation=feed.generation,
        total_lessons=feed.total_lessons,
        returned_lessons=feed.returned_lessons,
        lessons=[
            ExternalLessonResponse(
                id=lesson.id,
                text=lesson.text,
                title=lesson.title,
                topic=lesson.topic,
                source=lesson.source,
                importance=lesson.importance,
                tags=lesson.tags,
                date=lesson.date,
                created_at=lesson.created_at,
            )
            for lesson in feed.lessons
        ],
    )


def _runtime_path_response(
    description: RuntimePathDescription,
    *,
    path_override: Path | None = None,
    runtime_override: bool = False,
) -> RuntimePathResponse:
    path = path_override if path_override is not None else description.path
    if runtime_override:
        provenance = RuntimePathProvenanceResponse(
            kind="runtime_override",
            variable=None,
            deprecated=False,
        )
    else:
        provenance = RuntimePathProvenanceResponse(
            kind=description.provenance.kind,
            variable=description.provenance.variable,
            deprecated=description.provenance.deprecated,
        )

    kind: Literal["directory", "file"] = (
        "directory"
        if description.key in {"vault", "application_data", "cache"}
        else "file"
    )

    return RuntimePathResponse(
        key=description.key,
        path=str(path),
        role=description.role,
        exists=path.is_dir() if kind == "directory" else path.is_file(),
        kind=kind,
        provenance=provenance,
    )


def _runtime_paths_for_api() -> List[RuntimePathResponse]:
    try:
        descriptions = {item.key: item for item in describe_runtime_paths()}
    except VaultRegistryError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    output: List[RuntimePathResponse] = []
    for key in (
        "vault",
        "application_data",
        "vault_registry",
        "lesson_projection",
        "candidate_staging",
        "duplicate_decisions",
        "cache",
        "topic_model",
    ):
        description = descriptions[key]

        if key == "lesson_projection" and DATA_PATH is not None:
            output.append(
                _runtime_path_response(
                    description,
                    path_override=DATA_PATH,
                    runtime_override=True,
                )
            )
            continue

        if key == "topic_model" and MODEL_PATH is not None:
            output.append(
                _runtime_path_response(
                    description,
                    path_override=MODEL_PATH,
                    runtime_override=True,
                )
            )
            continue

        output.append(_runtime_path_response(description))

    return output


def _health_from_runtime_paths(
    paths: List[RuntimePathResponse],
) -> HealthResponse:
    by_key = {item.key: item for item in paths}
    return HealthResponse(
        status="ok",
        has_data=by_key["lesson_projection"].exists,
        has_model=by_key["topic_model"].exists,
    )


@app.get("/runtime/info", response_model=RuntimeInfoResponse)
def runtime_info() -> RuntimeInfoResponse:
    """Return bounded application identity used by the installed GUI."""
    return RuntimeInfoResponse(version=__version__)


@app.get("/settings/runtime", response_model=SettingsRuntimeResponse)
def settings_runtime() -> SettingsRuntimeResponse:
    """Return effective runtime configuration without mutating local state."""
    paths = _runtime_paths_for_api()
    return SettingsRuntimeResponse(
        version=__version__,
        health=_health_from_runtime_paths(paths),
        paths=paths,
    )


@app.get("/about", response_model=AboutResponse)
def about() -> AboutResponse:
    """Return bounded product identity and support metadata."""
    return AboutResponse(
        product_name="LeLe Manager",
        version=__version__,
        tagline="Your local-first lessons learned workspace",
        attribution="GiadaWare",
        license_id="MIT",
        license_summary=(
            "Open-source software distributed under the MIT License."
        ),
        license_url="/app/LICENSE",
        local_first_statement=(
            "LeLe Manager itself introduces no account, telemetry, cloud "
            "storage, or remote knowledge service."
        ),
        repository_url="https://github.com/gcomneno/lele-manager",
        issue_tracker_url="https://github.com/gcomneno/lele-manager/issues",
        releases_url="https://github.com/gcomneno/lele-manager/releases",
        changelog_url=(
            "https://github.com/gcomneno/lele-manager/blob/main/CHANGELOG.md"
        ),
        documentation_url=(
            "https://github.com/gcomneno/lele-manager/blob/main/"
            "docs/gui-user-guide.md"
        ),
        python_version=platform.python_version(),
        platform_system=platform.system(),
        platform_release=platform.release(),
    )


@app.get("/diagnostics/preview", response_model=DiagnosticsPreviewResponse)
def diagnostics_preview() -> DiagnosticsPreviewResponse:
    """Return the exact bounded diagnostic payload available for export."""
    paths = _runtime_paths_for_api()
    return DiagnosticsPreviewResponse(
        product_name="LeLe Manager",
        version=__version__,
        python_version=platform.python_version(),
        platform_system=platform.system(),
        platform_release=platform.release(),
        health=_health_from_runtime_paths(paths),
        paths=paths,
    )


def _count_vault_markdown_files(node: object) -> int:
    if not isinstance(node, dict):
        return 0
    if node.get("type") == "file":
        return 1
    children = node.get("children")
    if not isinstance(children, list):
        return 0
    return sum(_count_vault_markdown_files(child) for child in children)


@app.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary() -> DashboardSummaryResponse:
    """Return bounded, side-effect-free facts used by the product dashboard."""
    context = get_active_vault_context()
    health_state = _health_from_context(context)
    vault_exists = context.vault_dir.is_dir()

    vault_markdown_files: Optional[int] = None
    if vault_exists:
        tree = build_vault_tree(context.vault_dir)
        vault_markdown_files = _count_vault_markdown_files(tree.to_dict())

    stats: Optional[StatsSummaryResponse] = None
    if health_state.has_data:
        stats = _stats_summary_from_context(context)

    candidates: Optional[DashboardCandidateSummary]
    try:
        staged_candidates = JsonCandidateRepository(context.candidates_path).list()
    except CandidateRepositoryError:
        candidates = None
    else:
        counts = {state: 0 for state in CandidateState}
        for candidate in staged_candidates:
            counts[candidate.state] += 1
        candidates = DashboardCandidateSummary(
            total=len(staged_candidates),
            staged=counts[CandidateState.STAGED],
            in_review=counts[CandidateState.IN_REVIEW],
            rejected=counts[CandidateState.REJECTED],
            approved=counts[CandidateState.APPROVED],
        )

    return DashboardSummaryResponse(
        health_status=health_state.status,
        vault_exists=vault_exists,
        vault_markdown_files=vault_markdown_files,
        projection_exists=health_state.has_data,
        model_exists=health_state.has_model,
        stats=stats,
        candidates=candidates,
    )


def _health_from_context(context: ActiveVaultContext) -> HealthResponse:
    return HealthResponse(
        status="ok",
        has_data=context.projection_path.exists(),
        has_model=context.topic_model_path.exists(),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Stato rapido del servizio: dati e modello presenti/sì-no.
    """
    return _health_from_context(get_active_vault_context())


@app.get("/duplicates", response_model=DuplicateReportResponse)
def duplicates(
    min_score: float = Query(
        default=DEFAULT_MIN_SCORE,
        ge=0.0,
        le=1.0,
        description="Soglia euristica minima per le coppie near.",
    ),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=10_000,
        description="Numero massimo di coppie restituite, dopo l'ordinamento.",
    ),
    exact_only: bool = Query(
        default=False,
        description="Rileva solo duplicati esatti senza richiedere il modello.",
    ),
) -> DuplicateReportResponse:
    """Analyse all candidates, suppress valid decisions, then apply display limit."""
    context = get_active_vault_context()
    df = load_lessons_df(context)
    transformer = None
    feature_matrix = None
    if not exact_only and len(df) > 1:
        index = build_similarity_index(df, context)
        transformer = index.transformer
        feature_matrix = index.feature_matrix
    report = find_duplicates(
        df,
        transformer=transformer,
        feature_matrix=feature_matrix,
        min_score=min_score,
        exact_only=exact_only,
        limit=None,
    )
    vault_dir = context.vault_dir
    store = DuplicateDecisionStore(get_duplicate_decisions_path())
    scope = context.duplicate_decision_scope
    suppressed_pairs = 0
    unresolved: list[DuplicatePairResponse] = []
    for pair in report.pairs:
        left_row = cast(Mapping[str, Any], df.iloc[pair.left_position].to_dict())
        right_row = cast(Mapping[str, Any], df.iloc[pair.right_position].to_dict())
        left_fingerprint = material_fingerprint(left_row)
        right_fingerprint = material_fingerprint(right_row)
        resolution_available, resolution_problem = _duplicate_pair_safety(
            pair.left_id, pair.right_id, vault_dir,
        )
        suppressed = False
        if pair.left_id and pair.right_id and pair.left_id != pair.right_id:
            try:
                suppressed = store.is_suppressed(
                    scope=scope, left_id=pair.left_id, left_fingerprint=left_fingerprint,
                    right_id=pair.right_id, right_fingerprint=right_fingerprint,
                )
            except DuplicateDecisionStoreError:
                # A corrupt workflow-state file must never make review unusable
                # nor silently overwrite itself on this read-only operation.
                suppressed = False
        if suppressed:
            suppressed_pairs += 1
            continue
        unresolved.append(DuplicatePairResponse(**{
            **pair.to_dict(),
            "left_fingerprint": left_fingerprint,
            "right_fingerprint": right_fingerprint,
            "resolution_available": resolution_available,
            "resolution_problem": resolution_problem,
            "left_lesson": _row_to_duplicate_snapshot(left_row).model_dump(),
            "right_lesson": _row_to_duplicate_snapshot(right_row).model_dump(),
        }))
    shown = unresolved if limit is None else unresolved[:limit]
    exact_pairs = sum(item.kind == "exact" for item in unresolved)
    return DuplicateReportResponse(
        lessons_analyzed=report.lessons_analyzed,
        total_pairs=len(unresolved), exact_pairs=exact_pairs,
        near_pairs=len(unresolved) - exact_pairs, min_score=min_score,
        exact_only=exact_only, suppressed_pairs=suppressed_pairs, pairs=shown,
    )


@app.post("/duplicates/not-duplicates", response_model=DuplicateDecisionResponse)
def mark_not_duplicates(body: DuplicateNotDuplicatesRequest) -> DuplicateDecisionResponse:
    available, problem = _duplicate_pair_safety(body.left_id, body.right_id)
    if not available:
        raise _duplicate_error(409, "duplicate_pair_ambiguous", problem or "Ambiguous pair")
    try:
        context = get_active_vault_context()
        vault_dir = context.vault_dir
        left = _canonical_duplicate_lesson(vault_dir, body.left_id)
        right = _canonical_duplicate_lesson(vault_dir, body.right_id)
    except FileNotFoundError as exc:
        raise _duplicate_error(404, "vault_not_found", "The configured Markdown vault was not found.") from exc
    except _CanonicalDuplicateIdentityError as exc:
        if str(exc) == "not_found":
            raise _duplicate_error(404, "duplicate_pair_not_found", "One canonical lesson was not found.") from exc
        raise _duplicate_error(409, "duplicate_pair_ambiguous", "Canonical identity must be repaired before resolving this pair.") from exc
    if material_fingerprint(left) != body.left_fingerprint or material_fingerprint(right) != body.right_fingerprint:
        raise _duplicate_error(409, "duplicate_pair_stale", "One or both canonical lessons changed; refresh duplicate review.")
    try:
        decision = DuplicateDecisionStore(get_duplicate_decisions_path()).save_not_duplicates(
            scope=context.duplicate_decision_scope, left_id=body.left_id,
            left_fingerprint=body.left_fingerprint, right_id=body.right_id,
            right_fingerprint=body.right_fingerprint,
        )
    except DuplicateDecisionStoreError as exc:
        raise _duplicate_error(503, "duplicate_decision_store_failed", "The duplicate decision could not be saved.") from exc
    return DuplicateDecisionResponse(**decision.__dict__)


@app.post("/duplicates/merge", response_model=DuplicateMergeResponse)
def merge_duplicates(body: DuplicateMergeRequest) -> DuplicateMergeResponse:
    """Write a human-reviewed survivor, delete only then, and refresh once."""
    context = get_active_vault_context()
    vault_dir = context.vault_dir
    available, problem = _duplicate_pair_safety(
        body.survivor_id, body.superseded_id, vault_dir
    )
    if not available:
        raise _duplicate_error(409, "duplicate_pair_ambiguous", problem or "Ambiguous pair")
    try:
        survivor = _canonical_duplicate_lesson(vault_dir, body.survivor_id)
        superseded = _canonical_duplicate_lesson(vault_dir, body.superseded_id)
    except FileNotFoundError as exc:
        raise _duplicate_error(404, "vault_not_found", "The configured Markdown vault was not found.") from exc
    except _CanonicalDuplicateIdentityError as exc:
        code = "duplicate_pair_not_found" if str(exc) == "not_found" else "duplicate_pair_ambiguous"
        raise _duplicate_error(409 if code.endswith("ambiguous") else 404, code, "Canonical identity must be repaired before merging this pair.") from exc
    if (
        material_fingerprint(survivor) != body.expected_survivor_fingerprint
        or material_fingerprint(superseded) != body.expected_superseded_fingerprint
    ):
        raise _duplicate_error(409, "duplicate_pair_stale", "One or both canonical lessons changed; refresh duplicate review.")

    result = body.result
    try:
        write_canonical_lesson_source(
            vault_dir=vault_dir, lesson_id=body.survivor_id, body=result.text,
            topic=result.topic.strip(), source=result.source.strip() or "note",
            importance=int(result.importance),
            tags=[str(tag).strip() for tag in (result.tags or []) if str(tag).strip()],
            date=_lesson_date_or_today(result.date),
            title=result.title.strip() if result.title else None,
            invalidate_cache=invalidate_similarity_cache,
        )
    except CanonicalLessonWriteNotFoundError as exc:
        raise _duplicate_error(404, "duplicate_pair_not_found", "The surviving canonical lesson was not found.") from exc
    except CanonicalLessonWriteAmbiguousError as exc:
        raise _duplicate_error(409, "duplicate_pair_ambiguous", "Canonical identity must be repaired before merging this pair.") from exc
    except CanonicalLessonWriteStorageError as exc:
        raise _duplicate_error(503, "duplicate_merge_write_failed", "The resulting canonical lesson could not be saved.") from exc

    superseded_deleted = False
    failure: dict[str, str] | None = None
    try:
        delete_canonical_lesson_source(
            vault_dir=vault_dir, lesson_id=body.superseded_id,
            invalidate_cache=invalidate_similarity_cache,
        )
        superseded_deleted = True
    except (LessonDeletionNotFoundError, LessonDeletionStorageError):
        failure = {
            "code": "duplicate_merge_superseded_delete_failed",
            "message": "The result was saved, but the superseded canonical lesson could not be deleted.",
        }

    response = DuplicateMergeResponse(
        completed=superseded_deleted,
        survivor_id=body.survivor_id,
        survivor_written=True,
        superseded_id=body.superseded_id,
        superseded_deleted=superseded_deleted,
        refresh_outcome=DuplicateMergeRefreshOutcomeResponse(attempted=True, refreshed=False),
        failure=failure,
    )
    try:
        _sync_vault_import(context)
    except Exception as exc:
        raise _duplicate_error(
            503, "duplicate_merge_refresh_failed",
            "Canonical merge changes succeeded, but derived data could not be refreshed.",
            response.model_dump(),
        ) from exc
    return response.model_copy(
        update={"refresh_outcome": DuplicateMergeRefreshOutcomeResponse(attempted=True, refreshed=True)}
    )


@app.get("/lessons", response_model=List[LessonSearchResult])
def list_lessons(
    q: Optional[str] = Query(
        default=None,
        description="Filtro testuale (substring case-insensitive sul campo text).",
    ),
    topic: Optional[str] = Query(
        default=None,
        description="Filtra per topic esatto.",
    ),
    source: Optional[str] = Query(
        default=None,
        description="Filtra per source esatto.",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Numero massimo di risultati.",
    ),
) -> List[LessonSearchResult]:
    """
    Lista/cerca LeLe sul dataset attuale.
    Filtri applicati in sequenza e normalizzazione dei campi per evitare problemi
    di NA/NaT con Pydantic.
    """
    df = load_lessons_df()

    if df.empty:
        return []

    # Filtro testuale
    if q:
        q_lower = q.lower()
        df = df[df["text"].astype(str).str.lower().str.contains(q_lower, na=False)]

    # Filtro per topic
    if topic:
        df = df[df["topic"].astype(str) == topic]

    # Filtro per source
    if source:
        df = df[df["source"].astype(str) == source]

    # Limite
    df = df.head(limit)

    if df.empty:
        return []

    records = df.to_dict(orient="records")
    results: List[LessonSearchResult] = [_row_to_search_result(row) for row in records]

    return results


@app.post("/lessons/search", response_model=List[LessonSearchResult])
def search_lessons(body: LessonSearchRequest) -> List[LessonSearchResult]:
    """Ricerca avanzata sulle lessons via POST.

    Applica filtri su testo, topic, source e importance, riutilizzando la
    stessa normalizzazione di GET /lessons.
    """
    df = load_lessons_df()
    if df.empty:
        return []

    df = df.copy()

    # Filtro testo (q)
    if body.q:
        q_lower = body.q.lower()
        df = df[df["text"].astype(str).str.lower().str.contains(q_lower, na=False)]

    # Filtro topic_in
    if body.topic_in:
        df = df[df["topic"].astype(str).isin(body.topic_in)]

    # Filtro source_in
    if body.source_in:
        df = df[df["source"].astype(str).isin(body.source_in)]

    # Filtro importance range
    if body.importance_gte is not None or body.importance_lte is not None:
        importance = df.get("importance")
        if importance is None:
            df["importance"] = pd.NA
        else:
            df["importance"] = pd.to_numeric(importance, errors="coerce")

        if body.importance_gte is not None:
            df = df[df["importance"] >= body.importance_gte]

        if body.importance_lte is not None:
            df = df[df["importance"] <= body.importance_lte]

    # Deterministic ordering (#29): importance DESC (NaN last), created_at DESC (NaT last), id ASC
    if "importance" not in df.columns:
        df["importance"] = pd.NA
    if "date" not in df.columns:
        df["date"] = pd.NA
    if "id" not in df.columns:
        df["id"] = ""

    df["_importance_num"] = pd.to_numeric(df["importance"], errors="coerce")
    if "created_at" not in df.columns:
        df["created_at"] = pd.NA
    df["_created_at_dt"] = _safe_dt_series(df["created_at"])
    df["_id_sort"] = _safe_str_series(df["id"])

    df = df.sort_values(
        by=["_importance_num", "_created_at_dt", "_id_sort"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",  # stable sort for determinism
    )
    df = df.drop(
        columns=["_importance_num", "_created_at_dt", "_id_sort"], errors="ignore"
    )

    # Limit
    df = df.head(body.limit)

    if df.empty:
        return []

    records = df.to_dict(orient="records")
    results: List[LessonSearchResult] = [_row_to_search_result(row) for row in records]
    return results


def _export_filters_summary(body: ExportSearchRequest) -> str:
    parts: List[str] = []
    if body.q:
        parts.append(f"q={body.q!r}")
    if body.topic_in:
        parts.append(f"topic_in={body.topic_in}")
    if body.source_in:
        parts.append(f"source_in={body.source_in}")
    if body.importance_gte is not None:
        parts.append(f"importance_gte={body.importance_gte}")
    if body.importance_lte is not None:
        parts.append(f"importance_lte={body.importance_lte}")
    if body.ids_in:
        parts.append(f"ids_in={len(body.ids_in)} ids")
    parts.append(f"limit={body.limit}")
    return ", ".join(parts) if parts else "(nessun filtro)"


@app.post("/export/search")
def export_search(
    body: ExportSearchRequest,
    format: Literal["markdown", "json"] = Query(
        default="markdown",
        description="markdown → text/markdown; json → {markdown, n_lessons}.",
    ),
):
    """Esporta i risultati di una ricerca come documento Markdown."""
    search_body = LessonSearchRequest(
        q=body.q,
        topic_in=body.topic_in,
        source_in=body.source_in,
        importance_gte=body.importance_gte,
        importance_lte=body.importance_lte,
        limit=body.limit,
    )
    results = search_lessons(search_body)
    if body.ids_in:
        allowed = {str(i) for i in body.ids_in}
        results = [r for r in results if r.id in allowed]

    markdown = search_results_to_markdown(
        [r.model_dump() for r in results],
        include_frontmatter=body.include_frontmatter,
        filters_summary=_export_filters_summary(body),
    )

    if format == "json":
        return ExportSearchResponse(markdown=markdown, n_lessons=len(results))

    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


@app.get(
    "/lessons/{lesson_id:path}/similar",
    response_model=SimilarResponse,
    response_model_exclude_none=True,
)
def similar_lessons(
    lesson_id: str,
    context: Annotated[ActiveVaultContext, Depends(get_active_vault_context)],
    explain: bool = Query(
        default=False, description="Se true, include meta e rank per debug."
    ),
    top_k: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Numero massimo di LeLe simili da restituire.",
    ),
    min_score: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Soglia minima di similarità (coseno).",
    ),
) -> SimilarResponse:
    """
    Restituisce LeLe simili a quella indicata, usando il modello di similarità.
    """
    df = load_lessons_df(context)
    if df.empty:
        raise HTTPException(
            status_code=400, detail="Dataset vuoto, nessuna LeLe disponibile."
        )

    matches = df[df["id"].astype(str) == lesson_id]
    if matches.empty:
        raise HTTPException(
            status_code=404, detail=f"LeLe con id={lesson_id!r} non trovata."
        )

    query_text = str(matches.iloc[0]["text"])

    index = build_similarity_index(df, context)
    results_raw = similar_by_lesson_id(
        df=df,
        lesson_id=lesson_id,
        transformer=index.transformer,
        top_k=top_k,
        min_score=min_score,
    )
    # Togli eventuale self-match se costruito usando il testo della stessa LeLe
    filtered = [r for r in results_raw if r.lesson_id != lesson_id]

    query_row = matches.iloc[0]
    query_topic = _to_optional_str(query_row.get("topic"))
    query_tags = _normalize_tags(query_row.get("tags"))

    items = _build_similar_items(
        df, filtered, explain=explain, query_tags=query_tags if explain else None
    )
    meta = _build_similar_meta(
        explain=explain,
        top_k=top_k,
        min_score=min_score,
        query_topic=query_topic if explain else None,
        query_tags=query_tags if explain else None,
        context=context,
    )

    return SimilarResponse(
        query=query_text,
        results=items,
        meta=meta,
    )


@app.get("/lessons/{lesson_id:path}", response_model=Lesson)
def get_lesson(lesson_id: str) -> Lesson:
    """
    Recupera una singola LeLe per ID.
    Normalizza i campi (NaN/NaT/Timestamp) per evitare ValidationError Pydantic.
    """
    return _get_lesson_from_context(lesson_id, get_active_vault_context())


def _get_lesson_from_context(
    lesson_id: str, context: ActiveVaultContext
) -> Lesson:
    """Read a lesson from an already captured vault snapshot."""
    df = load_lessons_df(context)
    if df.empty:
        raise HTTPException(status_code=404, detail="Nessuna LeLe presente.")

    matches = df[df["id"].astype(str) == lesson_id]
    if matches.empty:
        raise HTTPException(
            status_code=404, detail=f"LeLe con id={lesson_id!r} non trovata."
        )

    row = matches.iloc[0]

    topic_val = _to_optional_str(row.get("topic"))
    source_val = _to_optional_str(row.get("source"))
    date_val = _to_optional_str(row.get("date"))
    title_val = _to_optional_str(row.get("title"))
    lifecycle_val = normalize_lifecycle(row.get("lifecycle"))
    superseded_by_val = _to_optional_str(row.get("superseded_by"))

    raw_importance = row.get("importance")
    if raw_importance is None or (
        isinstance(raw_importance, float) and pd.isna(raw_importance)
    ):
        importance_val = None
    else:
        try:
            importance_val = int(raw_importance)
        except (TypeError, ValueError):
            importance_val = None

    raw_tags = row.get("tags")
    tags_val = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else None

    return Lesson(
        id=str(row["id"]),
        text=str(row["text"]),
        topic=topic_val,
        source=source_val,
        importance=importance_val,
        tags=tags_val,
        date=date_val,
        title=title_val,
        lifecycle=lifecycle_val,
        superseded_by=superseded_by_val,
    )


@app.post("/lessons", response_model=Lesson, status_code=201)
def add_lesson(lesson_in: LessonCreate) -> Lesson:
    """
    Aggiunge una nuova LeLe al dataset (append su lessons.jsonl (data path)).
    L'ID viene generato se non fornito.
    """
    lele_id = lesson_in.id or uuid.uuid4().hex
    payload = lesson_in.dict(exclude={"id"})
    if not payload.get("created_at"):
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
    lesson = Lesson(id=lele_id, **payload)
    append_lesson_to_jsonl(lesson)
    return lesson


@app.post("/similar", response_model=SimilarResponse, response_model_exclude_none=True)
def similar_from_text(
    body: SimilarTextRequest,
    context: Annotated[ActiveVaultContext, Depends(get_active_vault_context)],
    explain: bool = Query(
        default=False, description="Se true, include meta e rank per debug."
    ),
) -> SimilarResponse:
    """
    Similarità a partire da testo libero (non richiede lesson_id).
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must be non-empty")

    df = load_lessons_df(context)
    if df.empty:
        raise HTTPException(
            status_code=400, detail="Dataset vuoto, nessuna LeLe disponibile."
        )

    # build_similarity_index() gestisce 503 se manca il modello.
    index = build_similarity_index(df, context)  # cached
    results_raw = similar_by_text(
        df,
        text,
        transformer=index.transformer,
        top_k=body.top_k,
        min_score=body.min_score,
    )

    query_tags = _parse_frontmatter_tags(text) if explain else None
    items = _build_similar_items(
        df,
        results_raw,
        explain=explain,
        query_tags=query_tags if explain and query_tags else None,
    )
    meta = _build_similar_meta(
        explain=explain,
        top_k=body.top_k,
        min_score=body.min_score,
        query_tags=query_tags if explain and query_tags else None,
        context=context,
    )

    return SimilarResponse(query=text, results=items, meta=meta)


@app.post("/train/topic", response_model=TrainResponse)
def train_topic() -> TrainResponse:
    """
    Allena (o riallena) il topic model a partire da lessons.jsonl (data path)
    e salva la pipeline in models/topic_model.joblib.

    Hardening:
    - non deve mai tornare 500 per errori "utente" (es. 1 solo topic)
    - filtra righe senza text/topic validi
    """
    return _train_topic_for_context(get_active_vault_context())


def _train_topic_for_context(context: ActiveVaultContext) -> TrainResponse:
    """Train against one immutable projection/model context."""
    df = load_lessons_df(context)
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="Dataset vuoto: nessuna LeLe da usare per il training.",
        )

    # Usa solo righe addestrabili (evita topic 'nan' generato da astype(str) su NaN)
    df_train = df.dropna(subset=["text", "topic"]).copy()
    df_train = df_train[df_train["text"].astype(str).str.strip() != ""]

    if df_train.empty:
        raise HTTPException(
            status_code=400,
            detail="Nessuna riga valida per il training: servono 'text' e 'topic' non vuoti.",
        )

    try:
        pipeline = train_topic_model(df_train)
    except (ValueError, KeyError) as exc:
        # errori "utente": 400 con messaggio umano (no 500)
        msg = str(exc)
        low = msg.lower()

        # Caso classico: TF-IDF/CountVectorizer rimane senza termini dopo pruning (min_df/max_df)
        # -> vogliamo un messaggio "umano" che contenga segnali tipo "TF-IDF" / "vocabulary"
        if (
            ("no terms remain" in low)
            or ("after pruning" in low)
            or ("empty vocabulary" in low)
        ):
            detail = f"TF-IDF vocabulary empty: {msg}"
            raise HTTPException(status_code=400, detail=detail)

        raise HTTPException(status_code=400, detail=msg)

    model_path = context.topic_model_path
    _ensure_model_dir(model_path)
    save_topic_model(pipeline, str(model_path) if model_path else None)
    invalidate_similarity_cache()

    topics = sorted(df_train["topic"].astype(str).unique())
    return TrainResponse(
        message=f"Topic model allenato con successo e salvato in {model_path}",
        n_lessons=int(len(df_train)),
        topics=topics,
    )


def _sync_vault_import(
    context: ActiveVaultContext | None = None,
    *,
    invalidate_cache: Callable[[], None] | None = None,
) -> VaultImportResponse:
    context = context or get_active_vault_context()
    vault_dir = context.vault_dir
    if not vault_dir.is_dir():
        raise FileNotFoundError(f"Vault directory not found: {vault_dir}")
    data_path = context.projection_path
    prepare_scoped_mutation_path(data_path, "lesson projection")
    result = import_vault_to_jsonl(vault_dir, data_path)
    (invalidate_cache or invalidate_similarity_cache)()
    return VaultImportResponse(
        message=f"Import completato: {result['n_lessons']} LeLe",
        n_lessons=int(result["n_lessons"]),
        output_path=str(result["output_path"]),
        topics=list(result["topics"]),
    )


def _lesson_date_or_today(date_val: Optional[str]) -> str:
    if date_val and str(date_val).strip():
        return str(date_val).strip()
    return datetime.now(timezone.utc).date().isoformat()


def _write_lesson_to_vault(
    *,
    lesson_id: str,
    payload: LessonVaultWrite,
    relative_path: Optional[str] = None,
    context: ActiveVaultContext | None = None,
) -> Path:
    vault_dir = (context or get_active_vault_context()).vault_dir
    tags = payload.tags or []
    date_str = _lesson_date_or_today(payload.date)
    return write_lesson_markdown(
        vault_dir,
        lesson_id=lesson_id,
        body=payload.text,
        topic=payload.topic.strip(),
        source=payload.source.strip() or "note",
        importance=int(payload.importance),
        tags=[str(t).strip() for t in tags if str(t).strip()],
        date=date_str,
        title=payload.title.strip() if payload.title else None,
        relative_path=relative_path,
    )


def _lesson_delete_response(result: LessonDeletionResult) -> LessonDeleteResponse:
    return LessonDeleteResponse(
        lesson_id=result.lesson_id,
        relative_vault_path=result.relative_vault_path,
        canonical_deleted=result.canonical_deleted,
        refresh_outcome=RefreshOutcomeResponse(
            refreshed=result.refresh_outcome.refreshed,
        ),
    )


def _bulk_delete_response(
    *,
    requested_count: int,
    deleted: list[CanonicalLessonDeletionResult],
    failed: list[BulkLessonDeleteFailedItem],
    refresh_attempted: bool,
    refreshed: bool,
) -> BulkLessonDeleteResponse:
    return BulkLessonDeleteResponse(
        requested_count=requested_count,
        deleted=[
            BulkLessonDeleteDeletedItem(
                lesson_id=item.lesson_id,
                relative_vault_path=item.relative_vault_path,
            )
            for item in deleted
        ],
        failed=failed,
        refresh_outcome=BulkRefreshOutcomeResponse(
            attempted=refresh_attempted,
            refreshed=refreshed,
        ),
    )


def _raise_lesson_deletion_error(error: Exception) -> None:
    if isinstance(error, PartialLessonDeletionRefreshError):
        result = error.result
        raise HTTPException(
            status_code=503,
            detail={
                "code": "lesson_deleted_refresh_failed",
                "message": (
                    "The canonical lesson was deleted, but derived data could not "
                    "be refreshed."
                ),
                "recovery": {
                    "canonical_deleted": True,
                    "lesson_id": result.lesson_id,
                    "relative_vault_path": result.relative_vault_path,
                },
            },
        ) from error
    if isinstance(error, LessonDeletionNotFoundError):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "lesson_not_found",
                "message": "The canonical lesson was not found.",
            },
        ) from error
    if isinstance(error, LessonDeletionStorageError):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "lesson_delete_storage_failed",
                "message": "The canonical lesson could not be deleted.",
            },
        ) from error
    if isinstance(error, FileNotFoundError):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "vault_not_found",
                "message": "The configured Markdown vault was not found.",
            },
        ) from error
    raise error


@app.get("/vault/status", response_model=VaultStatusResponse)
def vault_status() -> VaultStatusResponse:
    context = get_active_vault_context()
    return VaultStatusResponse(
        vault_dir=str(context.vault_dir), exists=context.vault_dir.is_dir(),
        vault_id=context.vault_id, display_name=context.display_name,
    )


def _registry_item(item: object, active_id: str) -> VaultRegistryItemResponse:
    # RegisteredVault is intentionally kept out of the HTTP schema.
    vault = cast(Any, item)
    path = vault.path
    return VaultRegistryItemResponse(
        id=vault.id, name=vault.name, path=str(path), active=vault.id == active_id,
        available=path.is_dir(), lesson_count=None,
    )


def _registry_error(exc: VaultRegistryError) -> HTTPException:
    status = 404 if isinstance(exc, VaultNotFoundError) else 409 if isinstance(exc, VaultConflictError) else 503
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


def _snapshot_context_for_registered_vault(vault_id: str) -> ActiveVaultContext:
    """Resolve an explicit registry identity; never fall back to active Vault."""
    try:
        store = VaultRegistryStore()
        return store.safe_context_for_registered(vault_id)
    except VaultRegistryError as exc:
        raise _registry_error(exc) from exc


def _snapshot_preview_response(preview: RestorePreview) -> VaultRestorePreviewResponse:
    return VaultRestorePreviewResponse(
        plan_digest=preview.plan_digest,
        target_vault_id=preview.target_vault_id,
        target_name=preview.target_name,
        target_path=preview.target_path,
        source_vault_id=preview.source_vault_id,
        source_vault_name=preview.source_vault_name,
        canonical_file_count=preview.canonical_file_count,
        additions=list(preview.additions),
        replacements=list(preview.replacements),
        removals=list(preview.removals),
        unchanged=list(preview.unchanged),
        editorial_state=list(preview.editorial_state),
        derived_effects=list(preview.derived_effects),
    )


async def _snapshot_request_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    try:
        if content_length is not None and int(content_length) > MAX_ARTIFACT_SIZE:
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "snapshot_invalid", "message": "Snapshot artifact is empty or exceeds the upload limit."},
        )
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_ARTIFACT_SIZE:
            raise HTTPException(
                status_code=422,
                detail={"code": "snapshot_invalid", "message": "Snapshot artifact is empty or exceeds the upload limit."},
            )
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        raise HTTPException(
            status_code=422,
            detail={"code": "snapshot_invalid", "message": "Snapshot artifact is empty or exceeds the upload limit."},
        )
    return raw


def _snapshot_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SnapshotPlanStaleError):
        status = 409
    elif isinstance(exc, SnapshotTargetError):
        status = 409
    elif isinstance(exc, SnapshotRestoreError):
        status = 503
    else:
        status = 422
    detail: dict[str, object] = {"code": getattr(exc, "code", "snapshot_invalid"), "message": str(exc)}
    if isinstance(exc, SnapshotRestoreError):
        detail["recovery"] = {
            "canonical_restored": False,
            "rollback_succeeded": exc.rollback_succeeded,
        }
    return HTTPException(status_code=status, detail=detail)


def _transfer_preview_response(preview: TransferPreview) -> VaultTransferPreviewResponse:
    return VaultTransferPreviewResponse(
        plan_digest=preview.plan_digest,
        operation=preview.operation,
        source_vault_id=preview.source_vault_id,
        source_name=preview.source_name,
        source_path=preview.source_path,
        destination_vault_id=preview.destination_vault_id,
        destination_name=preview.destination_name,
        destination_path=preview.destination_path,
        items=[
            VaultTransferItemPreviewResponse(
                lesson_id=item.lesson_id,
                source_path=item.source_path,
                source_sha256=item.source_sha256,
                destination_path=item.destination_path,
                destination_sha256=item.destination_sha256,
                classification=item.classification,
                resolution=item.resolution,
                duplicate_lesson_ids=list(item.duplicate_lesson_ids),
            )
            for item in preview.items
        ],
    )


def _transfer_response(result: TransferResult) -> VaultTransferResponse:
    return VaultTransferResponse(
        preview=_transfer_preview_response(result.preview),
        items=[VaultTransferItemResultResponse(**item.__dict__) for item in result.items],
        destination_derived_reconciled=result.destination_derived_reconciled,
        destination_derived_error=result.destination_derived_error,
        source_derived_reconciled=result.source_derived_reconciled,
        source_derived_error=result.source_derived_error,
    )


def _transfer_error(exc: Exception) -> HTTPException:
    if isinstance(exc, VaultTransferPlanStaleError):
        status = 409
    elif isinstance(exc, VaultTransferConflictError):
        status = 409
    elif isinstance(exc, (SnapshotTargetError, VaultPathError)):
        status = 409
    else:
        status = 422
    return HTTPException(status_code=status, detail={"code": getattr(exc, "code", "vault_transfer_invalid"), "message": str(exc)})


@app.get("/vaults", response_model=list[VaultRegistryItemResponse])
def list_vaults() -> list[VaultRegistryItemResponse]:
    try:
        store = VaultRegistryStore()
        context = store.context()
        return [_registry_item(item, context.vault_id) for item in store.list()]
    except VaultRegistryError as exc:
        raise _registry_error(exc) from exc


@app.get("/vaults/{vault_id}/snapshot")
def download_vault_snapshot(vault_id: str) -> Response:
    """Create a portable backup for one explicit registered Vault."""
    context = _snapshot_context_for_registered_vault(vault_id)
    try:
        artifact = create_snapshot(context, DuplicateDecisionStore(get_duplicate_decisions_path()))
    except (SnapshotValidationError, SnapshotTargetError, DuplicateDecisionStoreError) as exc:
        raise _snapshot_error(exc) from exc
    filename = f"lele-vault-{context.vault_id}.snapshot.zip"
    return Response(
        content=artifact,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/vaults/{vault_id}/restore/preview", response_model=VaultRestorePreviewResponse)
async def preview_vault_restore(vault_id: str, request: Request) -> VaultRestorePreviewResponse:
    """Validate an uploaded snapshot and report exact-state effects without mutation."""
    context = _snapshot_context_for_registered_vault(vault_id)
    try:
        artifact = validate_snapshot(await _snapshot_request_body(request))
        preview = preview_restore(artifact, context, DuplicateDecisionStore(get_duplicate_decisions_path()))
        return _snapshot_preview_response(preview)
    except (SnapshotValidationError, SnapshotTargetError, DuplicateDecisionStoreError) as exc:
        raise _snapshot_error(exc) from exc


@app.post("/vaults/{vault_id}/restore", response_model=VaultRestoreResponse)
async def restore_vault_snapshot(
    vault_id: str,
    request: Request,
    plan_digest: str = Query(min_length=64, max_length=64),
) -> VaultRestoreResponse:
    """Restore only after a matching preview plan, then reconcile derived state."""
    # Resolve the registered target immediately before execution; registry
    # identity/path is retained and active selection is not changed.
    try:
        artifact = validate_snapshot(await _snapshot_request_body(request))
        # Validation can take time; resolve the registered target again before
        # deriving the plan that will authorize an actual mutation.
        store = VaultRegistryStore()
        context = store.safe_context_for_registered(vault_id)

        def reconcile(final_context: ActiveVaultContext) -> None:
            # A model trained for old Markdown can never survive a restore.
            invalidate_scoped_derived_artifact(final_context.topic_model_path, "topic model")
            _sync_vault_import(final_context)

        result = execute_restore(
            artifact,
            context,
            DuplicateDecisionStore(get_duplicate_decisions_path()),
            plan_digest=plan_digest,
            reconcile_derived=reconcile,
            resolve_current_target=lambda: store.safe_context_for_registered(vault_id),
            mutation_boundary=store.mutation_boundary,
        )
    except (SnapshotValidationError, SnapshotTargetError, SnapshotPlanStaleError, SnapshotRestoreError, DuplicateDecisionStoreError) as exc:
        raise _snapshot_error(exc) from exc
    return VaultRestoreResponse(
        canonical_restored=result.canonical_restored,
        rollback_succeeded=result.rollback_succeeded,
        derived_reconciled=result.derived_reconciled,
        derived_error=result.derived_error,
        preview=_snapshot_preview_response(result.preview),
    )


def _transfer_contexts(body: VaultTransferRequest) -> tuple[ActiveVaultContext, ActiveVaultContext]:
    source = _snapshot_context_for_registered_vault(body.source_vault_id)
    destination = _snapshot_context_for_registered_vault(body.destination_vault_id)
    if source.vault_id == destination.vault_id:
        raise HTTPException(status_code=422, detail={"code": "vault_transfer_invalid", "message": "source and destination Vaults must be distinct"})
    return source, destination


def _transfer_selections(body: VaultTransferRequest) -> tuple[tuple[str, Literal["transfer", "keep_destination", "skip"] | None], ...]:
    return tuple((item.lesson_id, item.resolution) for item in body.selections)


@app.post("/vault-transfers/preview", response_model=VaultTransferPreviewResponse)
def preview_vault_transfer(body: VaultTransferRequest) -> VaultTransferPreviewResponse:
    """Build a read-only, stateless plan for selected canonical lessons."""
    try:
        source, destination = _transfer_contexts(body)
        preview = preview_transfer(
            operation=body.operation, source=source, destination=destination,
            selections=_transfer_selections(body),
        )
    except (VaultTransferError, SnapshotTargetError) as exc:
        raise _transfer_error(exc) from exc
    return _transfer_preview_response(preview)


@app.get("/vault-transfers/sources/{vault_id}/lessons", response_model=list[VaultTransferSourceLessonResponse])
def list_vault_transfer_source_lessons(vault_id: str) -> list[VaultTransferSourceLessonResponse]:
    """Read-only canonical lesson selection list for one registered Vault."""
    try:
        context = _snapshot_context_for_registered_vault(vault_id)
        return [VaultTransferSourceLessonResponse(lesson_id=lesson_id, source_path=path) for lesson_id, path in list_transferable_lessons(context)]
    except (VaultTransferError, SnapshotTargetError) as exc:
        raise _transfer_error(exc) from exc


@app.post("/vault-transfers/execute", response_model=VaultTransferResponse)
def execute_vault_transfer(body: VaultTransferExecuteRequest) -> VaultTransferResponse:
    """Execute only a matching stateless preview; never consult active Vault."""
    try:
        source, destination = _transfer_contexts(body)

        def reconcile(context: ActiveVaultContext) -> None:
            # An old topic model cannot be authoritative for changed Markdown.
            invalidate_scoped_derived_artifact(context.topic_model_path, "topic model")
            _sync_vault_import(context, invalidate_cache=lambda: invalidate_similarity_cache_for_context(context))

        result = execute_transfer(
            operation=body.operation, source=source, destination=destination,
            selections=_transfer_selections(body), plan_digest=body.plan_digest,
            resolve_source=lambda: _snapshot_context_for_registered_vault(body.source_vault_id),
            resolve_destination=lambda: _snapshot_context_for_registered_vault(body.destination_vault_id),
            reconcile_destination=reconcile, reconcile_source=reconcile,
        )
    except (VaultTransferError, SnapshotTargetError) as exc:
        raise _transfer_error(exc) from exc
    return _transfer_response(result)


@app.post("/vaults/create", response_model=VaultRegistryItemResponse, status_code=201)
def create_vault(body: VaultRegistryMutation) -> VaultRegistryItemResponse:
    if body.path is None:
        raise HTTPException(status_code=422, detail="path is required")
    try:
        store = VaultRegistryStore()
        store.bootstrap()
        item = store.create(body.name, body.path)
        return _registry_item(item, store.active().id)
    except VaultRegistryError as exc:
        raise _registry_error(exc) from exc


@app.post("/vaults/register", response_model=VaultRegistryItemResponse, status_code=201)
def register_vault(body: VaultRegistryMutation) -> VaultRegistryItemResponse:
    if body.path is None:
        raise HTTPException(status_code=422, detail="path is required")
    try:
        store = VaultRegistryStore()
        store.bootstrap()
        item = store.register(body.name, body.path)
        return _registry_item(item, store.active().id)
    except VaultRegistryError as exc:
        raise _registry_error(exc) from exc


@app.patch("/vaults/{vault_id}", response_model=VaultRegistryItemResponse)
def rename_vault(vault_id: str, body: VaultRegistryMutation) -> VaultRegistryItemResponse:
    try:
        store = VaultRegistryStore()
        item = store.rename(vault_id, body.name)
        return _registry_item(item, store.active().id)
    except VaultRegistryError as exc:
        raise _registry_error(exc) from exc


@app.delete("/vaults/{vault_id}", status_code=204)
def remove_vault(vault_id: str) -> Response:
    try:
        VaultRegistryStore().remove(vault_id)
    except VaultRegistryError as exc:
        raise _registry_error(exc) from exc
    return Response(status_code=204)


@app.post("/vaults/{vault_id}/activate", response_model=VaultStatusResponse)
def activate_vault(vault_id: str) -> VaultStatusResponse:
    """Reconcile the target read-only before changing active identity."""
    try:
        store = VaultRegistryStore()
        with store.mutation_boundary():
            target = next((item for item in store.list() if item.id == vault_id), None)
            if target is None:
                raise VaultNotFoundError("Vault was not found")
            if not target.path.is_dir():
                raise VaultPathError("Vault path is unavailable")
            target_context = store.context_for(target)
            # Selection never repairs or writes canonical Markdown.
            import_vault_to_jsonl(
                target.path,
                target_context.projection_path,
                write_missing_frontmatter=False,
            )
            store.activate(vault_id)
        invalidate_similarity_cache()
        return VaultStatusResponse(vault_dir=str(target.path), exists=True, vault_id=target.id, display_name=target.name)
    except VaultRegistryError as exc:
        raise _registry_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "vault_activation_failed", "message": "Could not switch Vault; previous Vault remains active."}) from exc


@app.get("/vault/tree", response_model=VaultTreeResponse)
def vault_tree() -> VaultTreeResponse:
    vault_dir = get_active_vault_context().vault_dir
    if not vault_dir.is_dir():
        raise FileNotFoundError(f"Vault directory not found: {vault_dir}")
    tree = build_vault_tree(vault_dir)
    return VaultTreeResponse(vault_dir=str(vault_dir), tree=tree.to_dict())


@app.get("/vault/doctor", response_model=VaultDoctorReportResponse)
def vault_doctor() -> VaultDoctorReportResponse:
    """Inspect the configured vault without modifying it."""
    try:
        vault_dir = get_active_vault_context().vault_dir
        if not vault_dir.is_dir():
            raise FileNotFoundError(f"Vault directory not found: {vault_dir}")
        report = check_markdown_files([], vault_dir=vault_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DoctorOperationalError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return VaultDoctorReportResponse(**report.to_dict())


@app.post("/vault/import", response_model=VaultImportResponse)
def vault_import() -> VaultImportResponse:
    """Importa il vault Markdown nel dataset JSONL configurato."""
    try:
        return _sync_vault_import()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/vault/lessons", response_model=Lesson, status_code=201)
def create_vault_lesson(body: LessonVaultCreate) -> Lesson:
    """Crea una nuova LeLe come file `.md` nel vault e risincronizza il JSONL."""
    date_str = _lesson_date_or_today(body.date)
    topic = body.topic.strip()
    lesson_id = (body.id or "").strip()
    if not lesson_id:
        rel = default_relative_path(
            lesson_id=f"{topic}/{date_str}.lesson",
            topic=topic,
            date=date_str,
            title=body.title,
        )
        lesson_id = rel.removesuffix(".md")

    try:
        context = get_active_vault_context()
        _write_lesson_to_vault(lesson_id=lesson_id, payload=body, context=context)
        _sync_vault_import(context)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _get_lesson_from_context(lesson_id, context)


@app.put("/lessons/{lesson_id:path}", response_model=Lesson)
def update_lesson(lesson_id: str, body: LessonVaultWrite) -> Lesson:
    """Aggiorna una LeLe: write-back su vault `.md` + re-import JSONL."""
    try:
        context = get_active_vault_context()
        vault_dir = context.vault_dir
        existing = find_markdown_by_id(vault_dir, lesson_id)
        rel_path = existing.relative_to(vault_dir).as_posix() if existing else None
        _write_lesson_to_vault(
            lesson_id=lesson_id, payload=body, relative_path=rel_path, context=context
        )
        _sync_vault_import(context)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _get_lesson_from_context(lesson_id, context)


@app.delete("/lessons/{lesson_id:path}", response_model=LessonDeleteResponse)
def delete_lesson(lesson_id: str) -> LessonDeleteResponse:
    """Delete one canonical Markdown lesson, then refresh its projection."""
    try:
        context = get_active_vault_context()
        result = delete_canonical_lesson(
            vault_dir=context.vault_dir,
            lesson_id=lesson_id,
            refresh=lambda: _sync_vault_import(context),
            invalidate_cache=invalidate_similarity_cache,
        )
    except (
        FileNotFoundError,
        LessonDeletionNotFoundError,
        LessonDeletionStorageError,
        PartialLessonDeletionRefreshError,
    ) as exc:
        _raise_lesson_deletion_error(exc)
        raise AssertionError("unreachable")
    return _lesson_delete_response(result)


@app.post("/lessons/bulk-delete", response_model=BulkLessonDeleteResponse)
def bulk_delete_lessons(body: BulkLessonDeleteRequest) -> BulkLessonDeleteResponse:
    """Delete only the submitted canonical sources, then reconcile once.

    This is deliberately a non-transactional batch: individual canonical
    failures are reported while later requested targets continue to run.
    """
    try:
        context = get_active_vault_context()
        vault_dir = context.vault_dir
    except FileNotFoundError as exc:
        _raise_lesson_deletion_error(exc)
        raise AssertionError("unreachable")

    deleted: list[CanonicalLessonDeletionResult] = []
    failed: list[BulkLessonDeleteFailedItem] = []
    for lesson_id in body.lesson_ids:
        try:
            deleted.append(
                delete_canonical_lesson_source(
                    vault_dir=vault_dir,
                    lesson_id=lesson_id,
                    invalidate_cache=invalidate_similarity_cache,
                )
            )
        except LessonDeletionNotFoundError:
            failed.append(BulkLessonDeleteFailedItem(lesson_id=lesson_id, code="not_found"))
        except LessonDeletionStorageError:
            failed.append(
                BulkLessonDeleteFailedItem(lesson_id=lesson_id, code="storage_error")
            )

    if not deleted:
        return _bulk_delete_response(
            requested_count=len(body.lesson_ids),
            deleted=deleted,
            failed=failed,
            refresh_attempted=False,
            refreshed=False,
        )

    try:
        _sync_vault_import(context)
    except Exception as exc:
        recovery = _bulk_delete_response(
            requested_count=len(body.lesson_ids),
            deleted=deleted,
            failed=failed,
            refresh_attempted=True,
            refreshed=False,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "bulk_lessons_deleted_refresh_failed",
                "message": (
                    "Canonical lessons were deleted, but derived data could not be "
                    "refreshed."
                ),
                "recovery": recovery.model_dump(),
            },
        ) from exc

    return _bulk_delete_response(
        requested_count=len(body.lesson_ids),
        deleted=deleted,
        failed=failed,
        refresh_attempted=True,
        refreshed=True,
    )


@app.post("/ops/refresh", response_model=OpsRefreshResponse)
def ops_refresh(
    train: bool = Query(
        default=True, description="Se true, riallena anche il topic model."
    ),
) -> OpsRefreshResponse:
    """Import vault → JSONL e opzionalmente train topic model (come lele-api-refresh)."""
    context = get_active_vault_context()
    try:
        import_result = _sync_vault_import(context)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    train_result: Optional[TrainResponse] = None
    if train:
        train_result = _train_topic_for_context(context)

    return OpsRefreshResponse(import_result=import_result, train_result=train_result)


@app.get("/stats/summary", response_model=StatsSummaryResponse)
def stats_summary() -> StatsSummaryResponse:
    """Statistiche aggregate sul dataset LeLe (dashboard / CLI)."""
    return _stats_summary_from_dataframe(load_lessons_df())


def _stats_summary_from_context(context: ActiveVaultContext) -> StatsSummaryResponse:
    return _stats_summary_from_dataframe(load_lessons_df(context))


def _stats_summary_from_dataframe(df: pd.DataFrame) -> StatsSummaryResponse:
    raw = compute_stats_summary(df)
    return StatsSummaryResponse(
        n_lessons=raw["n_lessons"],
        n_topics=raw["n_topics"],
        n_unique_tags=raw["n_unique_tags"],
        avg_text_length=raw["avg_text_length"],
        avg_importance=raw["avg_importance"],
        top_tags=[TagCount(**t) for t in raw["top_tags"]],
        by_topic=[TopicCount(**t) for t in raw["by_topic"]],
    )


@app.get("/editor/metadata-options", response_model=EditorMetadataOptionsResponse)
def editor_metadata_options() -> EditorMetadataOptionsResponse:
    """Complete read-only metadata facets for Editor suggestions.

    This deliberately reads the same active projection as the GUI. It does not
    import the vault, train a model, or mutate canonical Markdown.
    """
    raw = compute_metadata_options(load_lessons_df())
    return EditorMetadataOptionsResponse(
        topics=[MetadataOption(**item) for item in raw["topics"]],
        tags=[MetadataOption(**item) for item in raw["tags"]],
        sources=[MetadataOption(**item) for item in raw["sources"]],
    )


@app.get("/stats/timeline", response_model=TimelineResponse)
def stats_timeline(
    group_by: Literal["year", "month", "topic"] = Query(
        default="month",
        description="Raggruppamento: year, month, topic.",
    ),
) -> TimelineResponse:
    """Timeline acquisizione conoscenza, raggruppata per periodo o topic."""
    df = load_lessons_df()
    raw = compute_timeline(df, group_by=group_by)
    return TimelineResponse(
        group_by=raw["group_by"],
        buckets=[TimelineBucket(**b) for b in raw["buckets"]],
    )


@app.get("/ui", include_in_schema=False)
def ui_deprecated() -> RedirectResponse:
    """Deprecated: reindirizza alla GUI su /app/."""
    return RedirectResponse(url="/app/#/", status_code=307)


@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/app/")


if GUI_DIR is not None:
    _gui_dir = GUI_DIR
    _assets_dir = _gui_dir / "assets"
    if _assets_dir.is_dir():
        app.mount("/app/assets", StaticFiles(directory=_assets_dir), name="gui-assets")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/", include_in_schema=False)
    @app.get("/app/{full_path:path}", include_in_schema=False)
    def gui_app(full_path: str = "") -> FileResponse:
        index = _gui_dir / "index.html"

        if full_path:
            gui_root = _gui_dir.resolve()
            requested_file = (gui_root / full_path).resolve()

            try:
                requested_file.relative_to(gui_root)
            except ValueError:
                return FileResponse(index)

            if requested_file.is_file():
                return FileResponse(requested_file)

        return FileResponse(index)
else:

    @app.get("/app", include_in_schema=False)
    @app.get("/app/", include_in_schema=False)
    @app.get("/app/{full_path:path}", include_in_schema=False)
    def gui_not_built(full_path: str = "") -> None:
        raise HTTPException(
            status_code=503,
            detail="GUI non buildata. Esegui: ./scripts/build-gui.sh",
        )


# -----------------------------------------------------------------------------
# Similarity batch
# -----------------------------------------------------------------------------
@app.post(
    "/similar/batch",
    response_model=SimilarBatchResponse,
    response_model_exclude_none=True,
)
def similar_from_text_batch(
    body: SimilarBatchRequest,
    context: Annotated[ActiveVaultContext, Depends(get_active_vault_context)],
    explain: bool = Query(
        default=False, description="Se true, include meta e rank per debug."
    ),
) -> SimilarBatchResponse:
    """
    Similarità batch a partire da testi liberi.

    Non modifica il contratto di POST /similar.
    Preserva l'ordine delle richieste.
    """
    df = load_lessons_df(context)
    if df.empty:
        raise HTTPException(
            status_code=400, detail="Dataset vuoto, nessuna LeLe disponibile."
        )

    index = build_similarity_index(df, context)  # cached

    out_items: List[SimilarResponse] = []
    for req in body.items:
        text = req.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="text must be non-empty")

        results_raw = similar_by_text(
            df,
            text,
            transformer=index.transformer,
            top_k=req.top_k,
            min_score=req.min_score,
        )

        query_tags = _parse_frontmatter_tags(text) if explain else None
        items = _build_similar_items(
            df,
            results_raw,
            explain=explain,
            query_tags=query_tags if explain and query_tags else None,
        )
        meta = _build_similar_meta(
            explain=explain,
            top_k=req.top_k,
            min_score=req.min_score,
            query_tags=query_tags if explain and query_tags else None,
            context=context,
        )
        out_items.append(SimilarResponse(query=text, results=items, meta=meta))

    return SimilarBatchResponse(items=out_items)


# -----------------------------------------------------------------------------
# Editor integration (live suggest)
# -----------------------------------------------------------------------------
@app.post(
    "/editor/suggest", response_model=SimilarResponse, response_model_exclude_none=True
)
def editor_suggest(
    body: SimilarTextRequest,
    context: Annotated[ActiveVaultContext, Depends(get_active_vault_context)],
    explain: bool = Query(
        default=False, description="Se true, include meta e rank per debug."
    ),
) -> SimilarResponse:
    """
    Suggest LeLe simili mentre scrivo (editor integration).

    Thin wrapper: same behavior/contract as POST /similar.
    """
    return similar_from_text(body=body, context=context, explain=explain)
