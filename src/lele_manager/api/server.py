from __future__ import annotations

import json
import uuid
import pandas as pd

from importlib.metadata import PackageNotFoundError, version
from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime, timezone
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from threading import Lock

from lele_manager.core.analytics import compute_stats_summary, compute_timeline
from lele_manager.core.export import search_results_to_markdown
from lele_manager.core.config import resolve_data_path, resolve_model_path
from lele_manager.core.vault import (
    build_vault_tree,
    find_markdown_by_id,
    import_vault_to_jsonl,
    require_vault_dir,
    resolve_vault_dir,
    default_relative_path,
    write_lesson_markdown,
)
from lele_manager.ml.similarity import LessonSimilarityIndex
from lele_manager.ml.topic_model import (
    load_topic_model,
    save_topic_model,
    train_topic_model,
)
from lele_manager.ml.similarity_service import similar_by_text, similar_by_lesson_id


# Override espliciti (usati nei test via monkeypatch) — se None si usa default_*_path()
DATA_PATH: Path | None = None
MODEL_PATH: Path | None = None


def get_data_path() -> Path:
    return DATA_PATH if DATA_PATH is not None else resolve_data_path()

def get_model_path() -> Path:
    return MODEL_PATH if MODEL_PATH is not None else resolve_model_path()


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

# -----------------------------------------------------------------------------
# Schemi Pydantic
# -----------------------------------------------------------------------------
class LessonBase(BaseModel):
    text: str = Field(..., description="Testo della lesson learned")
    topic: Optional[str] = Field(None, description="Topic/macrocategoria (es. python, cpp, linux)")
    source: Optional[str] = Field(None, description="Origine: chatgpt, libro, esperimento, note, ...")
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


class LessonCreate(LessonBase):
    id: Optional[str] = Field(
        default=None,
        description="ID opzionale. Se non fornito, viene generato un UUID.",
    )


class Lesson(LessonBase):
    id: str


class LessonSearchResult(Lesson):
    pass


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
    items: List[SimilarBatchItemRequest] = Field(..., min_length=1, max_length=50, description="Batch di richieste di similarità.")


class SimilarBatchResponse(BaseModel):
    items: List[SimilarResponse]


class TrainResponse(BaseModel):
    message: str
    n_lessons: int
    topics: List[str]


class HealthResponse(BaseModel):
    status: str
    has_data: bool
    has_model: bool


class VaultStatusResponse(BaseModel):
    vault_dir: str
    exists: bool


class VaultTreeResponse(BaseModel):
    vault_dir: str
    tree: dict


class VaultImportResponse(BaseModel):
    message: str
    n_lessons: int
    output_path: str
    topics: List[str]


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
def _ensure_data_dir() -> None:
    get_data_path().parent.mkdir(parents=True, exist_ok=True)


def _ensure_model_dir() -> None:
    get_model_path().parent.mkdir(parents=True, exist_ok=True)


def load_lessons_df() -> pd.DataFrame:
    """
    Carica il JSONL delle LeLe in un DataFrame.
    Se il file non esiste, restituisce un DataFrame vuoto con colonne standard.
    Gestisce errori di parsing in modo esplicito.
    """
    data_path = get_data_path()
    if not data_path.exists():
        return pd.DataFrame(columns=["id", "text", "topic", "source", "importance", "tags", "date", "title", "created_at"])

    try:
        df = pd.read_json(data_path, lines=True)
    except ValueError as e:
        # Errore di parsing: JSONL corrotto o riga invalida
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel parsing di {data_path}: {e}",
        )

    # Assicuriamoci che almeno queste colonne esistano
    for col in ["id", "text", "topic", "source", "importance", "tags", "date", "title", "created_at"]:
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
    _ensure_data_dir()
    record = lesson.dict()
    data_path = get_data_path()
    with data_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _file_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def _similarity_cache_key(data_path: Path, model_path: Path) -> tuple[int, int]:
    return (_file_mtime_ns(data_path), _file_mtime_ns(model_path))


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
        df_indexed["topic"].fillna("").astype(str).to_dict() if "topic" in df_indexed.columns else {}
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
) -> Optional[SimilarMeta]:
    if not explain:
        return None
    data_path = get_data_path()
    model_path = get_model_path()
    data_mtime_ns, model_mtime_ns = _similarity_cache_key(data_path=data_path, model_path=model_path)
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


def build_similarity_index(df: pd.DataFrame):
    """
    Costruisce (o riusa) un LessonSimilarityIndex usando il topic model già allenato.
    Cached in API layer (#26).
    """
    if df.empty:
        raise HTTPException(status_code=400, detail="Nessuna LeLe presente nel dataset.")

    model_path = get_model_path()
    data_path = get_data_path()

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

    key = _similarity_cache_key(data_path=data_path, model_path=model_path)

    with app.state.sim_index_lock:
        if app.state.sim_index is not None and app.state.sim_index_key == key:
            return app.state.sim_index

        pipeline = load_topic_model(str(model_path) if model_path else None)
        index = LessonSimilarityIndex.from_topic_pipeline(df=df, pipeline=pipeline, id_column="id")

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


def _row_to_search_result(row: dict) -> LessonSearchResult:
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

    # importance: prova a convertirla, altrimenti None
    raw_importance = row.get("importance")
    if raw_importance is None or (isinstance(raw_importance, float) and pd.isna(raw_importance)):
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
    )


# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Stato rapido del servizio: dati e modello presenti/sì-no.
    """
    has_data = get_data_path().exists()
    has_model = get_model_path().exists()
    return HealthResponse(
        status="ok",
        has_data=has_data,
        has_model=has_model,
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
    df = df.drop(columns=["_importance_num", "_created_at_dt", "_id_sort"], errors="ignore")

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


@app.get("/lessons/{lesson_id:path}/similar", response_model=SimilarResponse, response_model_exclude_none=True)
def similar_lessons(
    lesson_id: str,
    explain: bool = Query(default=False, description="Se true, include meta e rank per debug."),
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
    df = load_lessons_df()
    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset vuoto, nessuna LeLe disponibile.")

    matches = df[df["id"].astype(str) == lesson_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"LeLe con id={lesson_id!r} non trovata.")

    query_text = str(matches.iloc[0]["text"])

    index = build_similarity_index(df)
    results_raw = similar_by_lesson_id(df=df, lesson_id=lesson_id, transformer=index.transformer, top_k=top_k, min_score=min_score)
    # Togli eventuale self-match se costruito usando il testo della stessa LeLe
    filtered = [r for r in results_raw if r.lesson_id != lesson_id]

    query_row = matches.iloc[0]
    query_topic = _to_optional_str(query_row.get("topic"))
    query_tags = _normalize_tags(query_row.get("tags"))

    items = _build_similar_items(df, filtered, explain=explain, query_tags=query_tags if explain else None)
    meta = _build_similar_meta(
        explain=explain,
        top_k=top_k,
        min_score=min_score,
        query_topic=query_topic if explain else None,
        query_tags=query_tags if explain else None,
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
    df = load_lessons_df()
    if df.empty:
        raise HTTPException(status_code=404, detail="Nessuna LeLe presente.")

    matches = df[df["id"].astype(str) == lesson_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"LeLe con id={lesson_id!r} non trovata.")

    row = matches.iloc[0]

    topic_val = _to_optional_str(row.get("topic"))
    source_val = _to_optional_str(row.get("source"))
    date_val = _to_optional_str(row.get("date"))
    title_val = _to_optional_str(row.get("title"))

    raw_importance = row.get("importance")
    if raw_importance is None or (isinstance(raw_importance, float) and pd.isna(raw_importance)):
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
def similar_from_text(body: SimilarTextRequest, explain: bool = Query(default=False, description="Se true, include meta e rank per debug.")) -> SimilarResponse:
    """
    Similarità a partire da testo libero (non richiede lesson_id).
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must be non-empty")

    df = load_lessons_df()
    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset vuoto, nessuna LeLe disponibile.")

    # build_similarity_index() gestisce 503 se manca il modello.
    index = build_similarity_index(df)  # cached
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
    df = load_lessons_df()
    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset vuoto: nessuna LeLe da usare per il training.")

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
        if ("no terms remain" in low) or ("after pruning" in low) or ("empty vocabulary" in low):
            detail = f"TF-IDF vocabulary empty: {msg}"
            raise HTTPException(status_code=400, detail=detail)

        raise HTTPException(status_code=400, detail=msg)

    _ensure_model_dir()
    model_path = get_model_path()
    save_topic_model(pipeline, str(model_path) if model_path else None)
    invalidate_similarity_cache()

    topics = sorted(df_train["topic"].astype(str).unique())
    return TrainResponse(
        message=f"Topic model allenato con successo e salvato in {model_path}",
        n_lessons=int(len(df_train)),
        topics=topics,
    )


def _sync_vault_import() -> VaultImportResponse:
    vault_dir = require_vault_dir()
    data_path = get_data_path()
    result = import_vault_to_jsonl(vault_dir, data_path)
    invalidate_similarity_cache()
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
) -> Path:
    vault_dir = require_vault_dir()
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


@app.get("/vault/status", response_model=VaultStatusResponse)
def vault_status() -> VaultStatusResponse:
    vault_dir = resolve_vault_dir()
    return VaultStatusResponse(vault_dir=str(vault_dir), exists=vault_dir.is_dir())


@app.get("/vault/tree", response_model=VaultTreeResponse)
def vault_tree() -> VaultTreeResponse:
    vault_dir = require_vault_dir()
    tree = build_vault_tree(vault_dir)
    return VaultTreeResponse(vault_dir=str(vault_dir), tree=tree.to_dict())


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
        _write_lesson_to_vault(lesson_id=lesson_id, payload=body)
        _sync_vault_import()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_lesson(lesson_id)


@app.put("/lessons/{lesson_id:path}", response_model=Lesson)
def update_lesson(lesson_id: str, body: LessonVaultWrite) -> Lesson:
    """Aggiorna una LeLe: write-back su vault `.md` + re-import JSONL."""
    try:
        vault_dir = require_vault_dir()
        existing = find_markdown_by_id(vault_dir, lesson_id)
        rel_path = existing.relative_to(vault_dir).as_posix() if existing else None
        _write_lesson_to_vault(lesson_id=lesson_id, payload=body, relative_path=rel_path)
        _sync_vault_import()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_lesson(lesson_id)


@app.post("/ops/refresh", response_model=OpsRefreshResponse)
def ops_refresh(
    train: bool = Query(default=True, description="Se true, riallena anche il topic model."),
) -> OpsRefreshResponse:
    """Import vault → JSONL e opzionalmente train topic model (come lele-api-refresh)."""
    try:
        import_result = _sync_vault_import()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    train_result: Optional[TrainResponse] = None
    if train:
        train_result = train_topic()

    return OpsRefreshResponse(import_result=import_result, train_result=train_result)


@app.get("/stats/summary", response_model=StatsSummaryResponse)
def stats_summary() -> StatsSummaryResponse:
    """Statistiche aggregate sul dataset LeLe (dashboard / CLI)."""
    df = load_lessons_df()
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
    _assets_dir = GUI_DIR / "assets"
    if _assets_dir.is_dir():
        app.mount("/app/assets", StaticFiles(directory=_assets_dir), name="gui-assets")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/", include_in_schema=False)
    @app.get("/app/{full_path:path}", include_in_schema=False)
    def gui_app(full_path: str = "") -> FileResponse:
        index = GUI_DIR / "index.html"
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
@app.post("/similar/batch", response_model=SimilarBatchResponse, response_model_exclude_none=True)
def similar_from_text_batch(body: SimilarBatchRequest, explain: bool = Query(default=False, description="Se true, include meta e rank per debug.")) -> SimilarBatchResponse:
    """
    Similarità batch a partire da testi liberi.

    Non modifica il contratto di POST /similar.
    Preserva l'ordine delle richieste.
    """
    df = load_lessons_df()
    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset vuoto, nessuna LeLe disponibile.")

    index = build_similarity_index(df)  # cached

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
        )
        out_items.append(SimilarResponse(query=text, results=items, meta=meta))

    return SimilarBatchResponse(items=out_items)

# -----------------------------------------------------------------------------
# Editor integration (live suggest)
# -----------------------------------------------------------------------------
@app.post("/editor/suggest", response_model=SimilarResponse, response_model_exclude_none=True)
def editor_suggest(
    body: SimilarTextRequest,
    explain: bool = Query(default=False, description="Se true, include meta e rank per debug."),
) -> SimilarResponse:
    """
    Suggest LeLe simili mentre scrivo (editor integration).

    Thin wrapper: same behavior/contract as POST /similar.
    """
    return similar_from_text(body=body, explain=explain)
