from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import pandas as pd

from lele_manager.ml.topic_model import (
    load_topic_model,
    save_topic_model,
    train_topic_model,
)

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Allena il topic model sulle lesson learned e salva la pipeline "
            "(feature + classificatore) su disco."
        )
    )

    parser.add_argument(
        "-i",
        "--input",
        default="data/lessons.jsonl",
        help="Percorso del dataset di lesson (JSONL con almeno 'text' e 'topic').",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="models/topic_model.joblib",
        help="Percorso file output per il modello allenato.",
    )
    parser.add_argument(
        "--text-column",
        default="text",
        help="Nome della colonna che contiene il testo della lesson (default: text).",
    )
    parser.add_argument(
        "--topic-column",
        default="topic",
        help="Nome della colonna che contiene il topic (default: topic).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sovrascrive il modello esistente se già presente.",
    )

    return parser.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise SystemExit(f"[errore] File input non trovato: {input_path}")

    if output_path.exists() and not args.overwrite:
        raise SystemExit(
            f"[errore] File modello esistente: {output_path} "
            "(usa --overwrite per sovrascrivere)."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[info] Carico dataset da: {input_path}")
    df = pd.read_json(input_path, lines=True)

    # Normalizza nomi colonne per il modello
    if args.text_column != "text" and args.text_column in df.columns:
        df = df.rename(columns={args.text_column: "text"})
    if args.topic_column != "topic" and args.topic_column in df.columns:
        df = df.rename(columns={args.topic_column: "topic"})

    if "text" not in df.columns or "topic" not in df.columns:
        raise SystemExit(
            "[errore] Il dataset deve contenere almeno le colonne "
            f"'text' (attuale: {args.text_column}) e 'topic' (attuale: {args.topic_column})."
        )

    # Filtra righe non utilizzabili
    before = len(df)
    df = df.dropna(subset=["text", "topic"])
    df = df[df["text"].astype(str).str.strip() != ""]
    after = len(df)

    if after == 0:
        raise SystemExit("[errore] Nessuna riga valida per l'addestramento.")

    print(f"[info] Righe totali: {before}, righe usate per training: {after}")

    # Allena modello
    print("[info] Alleno topic model...")
    pipeline = train_topic_model(df)

    # Salva modello
    save_topic_model(pipeline, str(output_path))
    print(f"[ok] Modello salvato in: {output_path}")

    # Check rapido di load
    _ = load_topic_model(str(output_path))
    print("[ok] Verifica caricamento modello riuscita.")

if __name__ == "__main__":
    main()
