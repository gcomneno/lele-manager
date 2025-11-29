from __future__ import annotations

import json
import uuid

from pathlib import Path
from typing import List, Optional

import pandas as pd

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from lele_manager.ml.similarity import LessonSimilarityIndex
from lele_manager.ml.topic_model import (
    load_topic_model,
    save_topic_model,
    train_topic_model,
)

# Percorsi “canonici” (come da CLI)
DATA_PATH = Path("data/lessons.jsonl")
MODEL_PATH = Path("models/topic_model.joblib")

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

class SimilarItem(BaseModel):
    id: str
    score: float
    text_preview: str

class SimilarResponse(BaseModel):
    query: str
    results: List[SimilarItem]

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
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

def _ensure_model_dir() -> None:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_lessons_df() -> pd.DataFrame:
    """
    Carica il JSONL delle LeLe in un DataFrame.
    Se il file non esiste, restituisce un DataFrame vuoto con colonne standard.
    Gestisce errori di parsing in modo esplicito.
    """
    if not DATA_PATH.exists():
        return pd.DataFrame(columns=["id", "text", "topic", "source", "importance", "tags", "date", "title"])

    try:
        df = pd.read_json(DATA_PATH, lines=True)
    except ValueError as e:
        # Errore di parsing: JSONL corrotto o riga invalida
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel parsing di {DATA_PATH}: {e}",
        )

    # Assicuriamoci che almeno queste colonne esistano
    for col in ["id", "text", "topic", "source", "importance", "tags", "date", "title"]:
        if col not in df.columns:
            df[col] = None

    return df

def append_lesson_to_jsonl(lesson: Lesson) -> None:
    """
    Appende una singola LeLe al file JSONL.
    """
    _ensure_data_dir()
    record = lesson.dict()
    with DATA_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def build_similarity_index(df: pd.DataFrame):
    """
    Costruisce un LessonSimilarityIndex usando il topic model già allenato.
    """
    if df.empty:
        raise HTTPException(status_code=400, detail="Nessuna LeLe presente nel dataset.")

    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Modello di topic non disponibile. Allena prima il modello con /train/topic.",
        )

    pipeline = load_topic_model(str(MODEL_PATH))
    index = LessonSimilarityIndex.from_topic_pipeline(df=df, pipeline=pipeline, id_column="id")
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

# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Stato rapido del servizio: dati e modello presenti/sì-no.
    """
    has_data = DATA_PATH.exists()
    has_model = MODEL_PATH.exists()
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

    results: List[LessonSearchResult] = []
    for row in records:
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

        results.append(
            LessonSearchResult(
                id=lele_id,
                text=text,
                topic=topic_val,
                source=source_val,
                importance=importance_val,
                tags=tags_val,
                date=date_val,
                title=title_val,
            )
        )

    return results

@app.get("/lessons/{lesson_id}", response_model=Lesson)
def get_lesson(lesson_id: str) -> Lesson:
    """
    Recupera una singola LeLe per ID.
    """
    df = load_lessons_df()
    if df.empty:
        raise HTTPException(status_code=404, detail="Nessuna LeLe presente.")

    matches = df[df["id"].astype(str) == lesson_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"LeLe con id={lesson_id!r} non trovata.")

    row = matches.iloc[0]
    return Lesson(
        id=str(row["id"]),
        text=str(row["text"]),
        topic=row.get("topic"),
        source=row.get("source"),
        importance=int(row["importance"]) if pd.notna(row.get("importance")) else None,
        tags=list(row["tags"]) if isinstance(row.get("tags"), list) else None,
        date=row.get("date"),
        title=row.get("title"),
    )

@app.post("/lessons", response_model=Lesson, status_code=201)
def add_lesson(lesson_in: LessonCreate) -> Lesson:
    """
    Aggiunge una nuova LeLe al dataset (append su data/lessons.jsonl).
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
    results_raw = index.most_similar(query_text=query_text, top_k=top_k, min_score=min_score)

    # Togli eventuale self-match se costruito usando il testo della stessa LeLe
    filtered = [r for r in results_raw if r.lesson_id != lesson_id]

    # Mappa id -> text per anteprima
    df_map = df.set_index("id")["text"].astype(str).to_dict()

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

@app.post("/train/topic", response_model=TrainResponse)
def train_topic() -> TrainResponse:
    """
    Allena (o riallena) il topic model a partire da data/lessons.jsonl
    e salva la pipeline in models/topic_model.joblib.
    """
    df = load_lessons_df()
    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset vuoto: nessuna LeLe da usare per il training.")

    # train_topic_model fa già i controlli su 'topic' e n. di classi
    pipeline = train_topic_model(df)

    _ensure_model_dir()
    save_topic_model(pipeline, str(MODEL_PATH))

    topics = sorted(df["topic"].dropna().astype(str).unique())
    return TrainResponse(
        message=f"Topic model allenato con successo e salvato in {MODEL_PATH}",
        n_lessons=int(len(df)),
        topics=topics,
    )
