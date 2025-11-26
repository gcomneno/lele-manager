from __future__ import annotations

from pathlib import Path
from typing import Sequence

import argparse

from lele_manager.storage import load_lessons, default_db_path

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lista le lesson learned con semplici filtri."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db_path(),
        help=f"Percorso database JSONL (default: {default_db_path()})",
    )
    parser.add_argument(
        "--source",
        "-s",
        help="Filtra per sorgente (es. chatgpt, libro, esperimento).",
    )
    parser.add_argument(
        "--topic",
        "-p",
        help="Filtra per topic (es. python, ml, devops).",
    )
    parser.add_argument(
        "--contains",
        "-c",
        help="Filtra per substring nel testo della lesson (case-insensitive).",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Numero massimo di lesson da mostrare (default: 20).",
    )
    return parser.parse_args(argv)

def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    lessons = load_lessons(args.db)

    def matches(lesson) -> bool:
        if args.source and lesson.source != args.source:
            return False
        if args.topic and lesson.topic != args.topic:
            return False
        if args.contains and args.contains.lower() not in lesson.text.lower():
            return False
        return True

    filtered = [l for l in lessons if matches(l)]
    filtered.sort(key=lambda l: l.created_at, reverse=True)

    count = 0
    for l in filtered[: args.limit]:
        count += 1
        ts = l.created_at.isoformat(timespec="seconds")
        tags = ", ".join(l.tags) if l.tags else "-"
        print(f"- [{l.id}] {ts}")
        print(f"  source={l.source} topic={l.topic} importance={l.importance} tags={tags}")
        print(f"  {l.text}")
        print()

    print(f"{count} lesson mostrate su {len(filtered)} trovate.")

if __name__ == "__main__":
    main()
