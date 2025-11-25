import argparse
import csv
import json

from pathlib import Path
from typing import Sequence

def convert_csv_to_json(
    input_path: Path,
    output_path: Path,
    encoding: str = "utf-8",
) -> int:
    """Converte un CSV in una lista JSON di record (dict)."""
    if not input_path.exists():
        raise FileNotFoundError(f"File CSV non trovato: {input_path}")

    with input_path.open("r", encoding=encoding, newline="") as f_in:
        reader = csv.DictReader(f_in)
        rows = list(reader)

    with output_path.open("w", encoding="utf-8") as f_out:
        json.dump(rows, f_out, ensure_ascii=False, indent=2)

    return len(rows)

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Converter CSV → JSON (lista di record).")
    parser.add_argument("input", type=Path, help="File CSV in input")
    parser.add_argument("output", type=Path, help="File JSON in output")
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding del CSV (default: utf-8)",
    )
    return parser.parse_args(argv)

def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    count = convert_csv_to_json(args.input, args.output, args.encoding)
    print(f"Convertiti {count} record da {args.input} a {args.output}")

if __name__ == "__main__":
    main()
