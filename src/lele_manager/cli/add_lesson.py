from __future__ import annotations

import argparse
import sys

from pathlib import Path
from typing import Sequence

from lele_manager.model import Lesson
from lele_manager.storage import append_lesson, default_db_path

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggiunge una nuova lesson learned al database JSONL."
    )
    parser.add_argument(
        "--text",
        "-t",
        help="Testo della lesson. Se omesso, viene letto da stdin (EOF per terminare).",
    )
    parser.add_argument(
        "--source",
        "-s",
        default="chatgpt",
        help='Sorgente (es. "chatgpt", "libro", "esperimento"). Default: chatgpt',
    )
    parser.add_argument(
        "--topic",
        "-p",
        default="misc",
        help='Topic principale (es. "python", "ml", "devops"). Default: misc',
    )
    parser.add_argument(
        "--importance",
        "-i",
        type=int,
        default=3,
        help="Importanza 1–5 (default: 3).",
    )
    parser.add_argument(
        "--tags",
        help='Lista di tag separati da virgola (es. "python,ml,pattern").',
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db_path(),
        help=f"Percorso database JSONL (default: {default_db_path()})",
    )
    return parser.parse_args(argv)

def read_text_from_stdin() -> str:
    print("Inserisci il testo della lesson, termina con EOF (Ctrl+D / Ctrl+Z):", file=sys.stderr)
    text = sys.stdin.read().strip()
    return text

def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    if args.text:
        text = args.text.strip()
    else:
        text = read_text_from_stdin()

    if not text:
        raise SystemExit("Testo della lesson vuoto, niente da salvare.")

    if args.importance < 1 or args.importance > 5:
        raise SystemExit("Importance deve essere tra 1 e 5.")

    tags = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    lesson = Lesson.new(
        source=args.source,
        topic=args.topic,
        importance=args.importance,
        text=text,
        tags=tags,
    )

    append_lesson(lesson, args.db)

    print(f"Lesson salvata con id={lesson.id} in {args.db}")

if __name__ == "__main__":
    main()
