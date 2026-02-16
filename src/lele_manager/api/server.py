from __future__ import annotations

import json
import uuid
import pandas as pd

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pathlib import Path
from fastapi.responses import HTMLResponse
from threading import Lock

from lele_manager.core.config import resolve_data_path, resolve_model_path
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


app = FastAPI(
    title="LeLe Manager API",
    description="API per gestire e cercare le Lesson Learned (LeLe).",
    version="0.2.0",
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


class SimilarItem(BaseModel):
    id: str
    score: float
    text_preview: str


class SimilarResponse(BaseModel):
    query: str
    results: List[SimilarItem]


class SimilarTextRequest(BaseModel):
    text: str = Field(..., description="Testo libero da confrontare.")
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class TrainResponse(BaseModel):
    message: str
    n_lessons: int
    topics: List[str]


class HealthResponse(BaseModel):
    status: str
    has_data: bool
    has_model: bool


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
        return pd.DataFrame(columns=["id", "text", "topic", "source", "importance", "tags", "date", "title"])

    try:
        df = pd.read_json(data_path, lines=True)
    except ValueError as e:
        # Errore di parsing: JSONL corrotto o riga invalida
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel parsing di {data_path}: {e}",
        )

    # Assicuriamoci che almeno queste colonne esistano
    for col in ["id", "text", "topic", "source", "importance", "tags", "date", "title"]:
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

    # Deterministic ordering (#29): importance DESC (NaN last), date DESC (NaT last), id ASC
    if "importance" not in df.columns:
        df["importance"] = pd.NA
    if "date" not in df.columns:
        df["date"] = pd.NA
    if "id" not in df.columns:
        df["id"] = ""

    df["_importance_num"] = pd.to_numeric(df["importance"], errors="coerce")
    df["_date_dt"] = _safe_dt_series(df["date"])
    df["_id_sort"] = _safe_str_series(df["id"])

    df = df.sort_values(
        by=["_importance_num", "_date_dt", "_id_sort"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",  # stable sort for determinism
    )
    df = df.drop(columns=["_importance_num", "_date_dt", "_id_sort"], errors="ignore")

    # Limit
    df = df.head(body.limit)

    if df.empty:
        return []

    records = df.to_dict(orient="records")
    results: List[LessonSearchResult] = [_row_to_search_result(row) for row in records]
    return results


@app.get("/lessons/{lesson_id}", response_model=Lesson)
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

    # Normalizza stringhe (gestisce NaN/NaT/Timestamp -> str o None)
    topic_val = _to_optional_str(row.get("topic"))
    source_val = _to_optional_str(row.get("source"))
    date_val = _to_optional_str(row.get("date"))
    title_val = _to_optional_str(row.get("title"))

    # importance robusta
    raw_importance = row.get("importance")
    if raw_importance is None or (isinstance(raw_importance, float) and pd.isna(raw_importance)):
        importance_val = None
    else:
        try:
            importance_val = int(raw_importance)
        except (TypeError, ValueError):
            importance_val = None

    # tags: solo se lista
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
    lesson = Lesson(id=lele_id, **lesson_in.dict(exclude={"id"}))
    append_lesson_to_jsonl(lesson)
    return lesson


@app.get("/lessons/{lesson_id}/similar", response_model=SimilarResponse)
def similar_lessons(
    lesson_id: str,
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

    # Mappa id -> text per anteprima
    df_map = df.set_index("id")["text"].fillna("").astype(str).to_dict()

    items: List[SimilarItem] = []
    for r in filtered:
        text = df_map.get(r.lesson_id, "")
        preview = text.replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."
        items.append(
            SimilarItem(
                id=str(r.lesson_id),
                score=float(r.score),
                text_preview=preview,
            )
        )

    return SimilarResponse(
        query=query_text,
        results=items,
    )


@app.post("/similar", response_model=SimilarResponse)
def similar_from_text(body: SimilarTextRequest) -> SimilarResponse:
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

    df_map = df.set_index("id")["text"].fillna("").astype(str).to_dict()

    items: List[SimilarItem] = []
    for r in results_raw:
        preview = df_map.get(r.lesson_id, "").replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."
        items.append(
            SimilarItem(
                id=str(r.lesson_id),
                score=float(r.score),
                text_preview=preview,
            )
        )

    return SimilarResponse(query=text, results=items)


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


@app.get("/ui", response_class=HTMLResponse)
def ui() -> HTMLResponse:
    ui_path = Path(__file__).with_name("ui.html")
    return HTMLResponse(ui_path.read_text(encoding="utf-8"))
