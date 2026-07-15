from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import pandas as pd

from lele_manager.application.dataframes import records_to_legacy_dataframe
from lele_manager.composition import projection_store
from lele_manager.core.projection_store import ProjectionStoreError
from lele_manager.core.config import default_data_path
from lele_manager.ml.similarity import LessonSimilarityIndex
from lele_manager.ml.similarity_service import similar_by_lesson_id, similar_by_text
from lele_manager.ml.topic_model import load_topic_model


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Suggerisce lesson simili a partire da un testo o da una lesson esistente."
        )
    )

    parser.add_argument(
        "-i",
        "--input",
        default=str(default_data_path()),
        help="Percorso del dataset di lesson (JSONL).",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="models/topic_model.joblib",
        help="Percorso del modello topic (pipeline joblib).",
    )
    parser.add_argument(
        "--id-column",
        default="id",
        help="Nome della colonna che identifica univocamente le lesson (default: id).",
    )
    parser.add_argument(
        "--text-column",
        default="text",
        help="Nome della colonna che contiene il testo della lesson (default: text).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Numero massimo di lesson simili da mostrare (default: 5).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Soglia minima di similarità coseno (default: 0.0).",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--text",
        default=None,
        help="Testo libero da usare come query di similarità.",
    )
    group.add_argument(
        "--from-id",
        default=None,
        help="ID di una lesson esistente da usare come query di similarità.",
    )

    return parser.parse_args(argv)


def _load_dataset(dataset_path: Path, text_column: str) -> pd.DataFrame:
    if not dataset_path.exists():
        raise SystemExit(f"[err] Dataset non trovato: {dataset_path}")

    try:
        df = records_to_legacy_dataframe(projection_store(dataset_path).snapshot().list())
    except (ProjectionStoreError, ValueError) as exc:
        raise SystemExit(f"[err] JSONL non valido o non leggibile: {exc}") from exc
    if df.empty:
        raise SystemExit("[err] Dataset vuoto: nessuna lesson disponibile.")

    if text_column not in df.columns:
        raise SystemExit(f"[err] Colonna testo '{text_column}' non trovata nel dataset.")

    # normalizza: il resto del codice assume che il testo sia in colonna "text"
    if text_column != "text":
        df = df.rename(columns={text_column: "text"})

    # evitiamo NaN -> "nan"
    df["text"] = df["text"].fillna("").astype(str)
    return df


def _get_query_text_from_id(df: pd.DataFrame, id_column: str, lesson_id: str) -> str:
    matches = df[df[id_column].astype(str) == str(lesson_id)]
    if matches.empty:
        raise SystemExit(f"[err] Lesson con {id_column}={lesson_id!r} non trovata nel dataset.")
    return str(matches.iloc[0]["text"])


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    dataset_path = Path(args.input)
    model_path = Path(args.model)

    print(f"[info] Carico dataset da: {dataset_path}")
    df = _load_dataset(dataset_path, args.text_column)

    if args.id_column not in df.columns:
        # non è obbligatoria per il training, ma lo è per l'output sensato
        print(
            f"[warn] Colonna ID '{args.id_column}' non trovata. "
            "Uso l'indice del DataFrame come ID."
        )
        df = df.reset_index().rename(columns={"index": args.id_column})

    print(f"[info] Carico modello da: {model_path}")
    pipeline = load_topic_model(str(model_path) if model_path else None)

    print("[info] Costruisco indice di similarità...")
    index = LessonSimilarityIndex.from_topic_pipeline(
        df=df,
        pipeline=pipeline,
        id_column=args.id_column,
    )

    # Determina la query
    query_text: str
    query_id: Optional[str] = None

    if args.text is not None:
        query_text = args.text
        print("[info] Query basata su testo esplicito (--text).")
        print("\n[info] Testo query:")
        print("------------------------------------------------------------")
        print(query_text)
        print("------------------------------------------------------------\n")

        results = similar_by_text(
            df=df,
            query_text=query_text,
            transformer=index.transformer,
            top_k=args.top_k,
            min_score=args.min_score,
        )
    else:
        query_id = str(args.from_id)
        query_text = _get_query_text_from_id(df, args.id_column, query_id)
        print(f"[info] Query basata su lesson esistente (--from-id={query_id}).")

        print("\n[info] Testo query:")
        print("------------------------------------------------------------")
        print(query_text)
        print("------------------------------------------------------------\n")

        results = similar_by_lesson_id(
            df=df,
            lesson_id=query_id,
            transformer=index.transformer,
            top_k=args.top_k,
            min_score=args.min_score,
        )

        # per coerenza con comportamento precedente: niente self-match
        results = [r for r in results if r.lesson_id != query_id]

    if not results:
        print("[info] Nessuna lesson simile trovata con i parametri attuali.")
        return

    print("[ok] Lesson simili trovate:\n")

    # Mappa ID → testo (già con colonna text normalizzata)
    df_id_map = df.set_index(args.id_column)["text"].astype(str).to_dict()

    for r in results:
        preview = df_id_map.get(r.lesson_id, "").replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "..."

        print(f"- {args.id_column}={r.lesson_id} | score={r.score:.3f}")
        print(f"  {preview}\n")


if __name__ == "__main__":
    main()
