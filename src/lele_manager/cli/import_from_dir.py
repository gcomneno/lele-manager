from __future__ import annotations

import argparse
import hashlib
import json
import yaml

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union
import datetime as _dt

DuplicatePolicy = Literal["overwrite", "skip", "error"]


@dataclass
class LeLeRecord:
    id: str
    text: str
    topic: Optional[str]
    source: Optional[str]
    importance: Optional[int]
    tags: List[str]
    date: Optional[str]
    title: Optional[str]
    path: str
    frontmatter: Dict[str, object]
    frontmatter_hash: str


# ---------------------------------------------------------------------------
# Frontmatter parsing / writing
# ---------------------------------------------------------------------------
def parse_markdown_with_frontmatter(content: str) -> Tuple[Dict[str, object], str]:
    """
    Ritorna (frontmatter_dict, body_text).

    Se non c'è frontmatter YAML valido, restituisce ({}, content).
    """
    lines = content.splitlines()
    if not lines:
        return {}, ""

    if not lines[0].strip().startswith("---"):
        # niente frontmatter
        return {}, content

    # Trova la seconda linea '---'
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip().startswith("---"):
            end_idx = i
            break

    if end_idx is None:
        # frontmatter malformato: trattiamo tutto come testo
        return {}, content

    fm_lines = lines[1:end_idx]
    body_lines = lines[end_idx + 1 :]

    fm_text = "\n".join(fm_lines)
    try:
        frontmatter = yaml.safe_load(fm_text) or {}
        if not isinstance(frontmatter, dict):
            frontmatter = {}
    except Exception:
        frontmatter = {}

    body = "\n".join(body_lines).lstrip("\n")
    return frontmatter, body


def render_markdown_with_frontmatter(frontmatter: Dict[str, object], body: str) -> str:
    """
    Ricostruisce il contenuto markdown con frontmatter YAML.
    Mantiene l'ordine di inserimento delle chiavi.
    """
    fm_text = yaml.safe_dump(frontmatter, sort_keys=False).rstrip()
    return f"---\n{fm_text}\n---\n\n{body.rstrip()}\n"


# ---------------------------------------------------------------------------
# Helper per ID, topic, hash
# ---------------------------------------------------------------------------
def derive_id_from_path(md_path: Path, root_dir: Path) -> str:
    """
    Deriva un ID leggibile dal path relativo (senza estensione).
    Esempio:
      root_dir = /foo/LeLeVault
      md_path = /foo/LeLeVault/cpp/2025-11-20.cin-vs-getline.md
      -> id = "cpp/2025-11-20.cin-vs-getline"
    """
    rel = md_path.relative_to(root_dir).as_posix()
    if rel.lower().endswith(".md"):
        rel = rel[:-3]
    return rel


def derive_topic(frontmatter: Dict[str, object], md_path: Path, default_topic: Optional[str]) -> Optional[str]:
    if "topic" in frontmatter and isinstance(frontmatter["topic"], str):
        t = frontmatter["topic"].strip()
        return t or None
    if default_topic:
        return default_topic
    # fallback: nome della directory immediata
    parent = md_path.parent.name
    return parent or None


def normalize_tags(value: Union[str, List[str], None]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        # tieni solo stringhe non vuote
        return [str(x).strip() for x in value if str(x).strip()]
    # se è stringa, prova a splittare su virgola
    txt = str(value)
    if "," in txt:
        return [part.strip() for part in txt.split(",") if part.strip()]
    return [txt.strip()] if txt.strip() else []


def _normalize_frontmatter_date(value: object) -> Optional[str]:
    """
    Normalizza 'date' dal frontmatter:
    - 'YYYY-MM-DD' (str) -> stessa stringa (strip)
    - datetime/date -> 'YYYY-MM-DD'
    - altri tipi -> None (si usa fallback dal filename)
    """
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    # PyYAML può parse-are '2025-01-01' come datetime.date
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    return None


def derive_date(frontmatter: Dict[str, object], md_path: Path) -> Optional[str]:
    # 1) dal frontmatter (normalizzato)
    if "date" in frontmatter:
        norm = _normalize_frontmatter_date(frontmatter.get("date"))
        if norm:
            return norm

    # 2) dal filename tipo "YYYY-MM-DD.slug.md"
    stem = md_path.stem  # es: "2025-11-20.cin-vs-getline"
    parts = stem.split(".")
    if parts and len(parts[0]) == 10 and parts[0].count("-") == 2:
        # controllo minimale
        return parts[0]
    return None


def compute_frontmatter_hash(frontmatter: Dict[str, object]) -> str:
    """
    Restituisce un hash stabile del frontmatter (solo metadati, no body).

    Nota: usiamo SHA-256 pur non avendo esigenze di sicurezza crittografica,
    così evitiamo i warning degli static analyzer (Bandit B324 su SHA-1).
    """
    # Dump YAML con chiavi ordinate per avere stabilità
    text = yaml.safe_dump(frontmatter, sort_keys=True)
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{h}"


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------
def import_from_dir(
    input_dir: Path,
    on_duplicate: DuplicatePolicy,
    default_source: Optional[str],
    default_importance: Optional[int],
    default_topic: Optional[str],
    write_missing_frontmatter: bool,
) -> Dict[str, LeLeRecord]:
    if not input_dir.is_dir():
        raise SystemExit(f"[errore] Directory di input non trovata: {input_dir}")

    records_by_id: Dict[str, LeLeRecord] = {}
    first_path_by_id: Dict[str, Path] = {}
    files_to_update: List[Tuple[Path, str]] = []

    md_files = sorted(input_dir.rglob("*.md"))

    if not md_files:
        print(f"[warn] Nessun file .md trovato sotto {input_dir}")
        return records_by_id

    print(f"[info] Trovati {len(md_files)} file .md sotto {input_dir}")

    for md_path in md_files:
        rel_path = md_path.relative_to(input_dir).as_posix()

        try:
            content = md_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"[warn] Impossibile leggere {rel_path} come UTF-8, salto.")
            continue

        frontmatter, body = parse_markdown_with_frontmatter(content)
        original_fm = dict(frontmatter)  # snapshot

        # ID
        raw_id = frontmatter.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            lele_id = raw_id.strip()
        else:
            lele_id = derive_id_from_path(md_path, input_dir)
            frontmatter["id"] = lele_id

        # topic
        topic = derive_topic(frontmatter, md_path, default_topic)
        if write_missing_frontmatter and ("topic" not in frontmatter) and topic is not None:
            frontmatter["topic"] = topic

        # source
        source: Optional[str]
        if "source" in frontmatter and isinstance(frontmatter["source"], str):
            source = frontmatter["source"].strip() or None
            if write_missing_frontmatter and source is None and default_source is not None:
                source = default_source
                frontmatter["source"] = source
        else:
            source = default_source
            if write_missing_frontmatter and default_source is not None and "source" not in frontmatter:
                frontmatter["source"] = default_source

        # importance
        importance: Optional[int]
        if "importance" in frontmatter:
            try:
                importance = int(frontmatter["importance"])  # type: ignore[arg-type]
            except (TypeError, ValueError):
                importance = default_importance
                if write_missing_frontmatter and default_importance is not None:
                    frontmatter["importance"] = int(default_importance)
        else:
            importance = default_importance
            if write_missing_frontmatter and default_importance is not None:
                frontmatter["importance"] = int(default_importance)

        # tags
        tags = normalize_tags(frontmatter.get("tags"))

        # date (normalizzata)
        date = derive_date(frontmatter, md_path)
        if write_missing_frontmatter:
            # normalizza il tipo (date/datetime -> string) se presente
            if "date" in frontmatter:
                norm = _normalize_frontmatter_date(frontmatter.get("date"))
                if norm and frontmatter.get("date") != norm:
                    frontmatter["date"] = norm
            # se manca, la deduciamo dal filename (se possibile)
            if "date" not in frontmatter and date is not None:
                frontmatter["date"] = date

        # title (opzionale)
        title = None
        if "title" in frontmatter and isinstance(frontmatter["title"], str):
            title = frontmatter["title"]

        # hash frontmatter
        frontmatter_hash = compute_frontmatter_hash(frontmatter)

        # body text pulito
        text = body.strip()

        record = LeLeRecord(
            id=lele_id,
            text=text,
            topic=topic,
            source=source,
            importance=importance,
            tags=tags,
            date=date,
            title=title,
            path=rel_path,
            frontmatter=frontmatter,
            frontmatter_hash=frontmatter_hash,
        )

        # Duplicati
        if lele_id in records_by_id:
            existing_path = first_path_by_id[lele_id]
            msg = (
                f"ID duplicato '{lele_id}' in {rel_path} "
                f"(già visto in {existing_path.relative_to(input_dir)})"
            )

            if on_duplicate == "error":
                raise SystemExit(f"[errore] {msg}")
            elif on_duplicate == "skip":
                print(f"[warn] {msg} -> skip nuovo file.")
                continue
            elif on_duplicate == "overwrite":
                print(f"[info] {msg} -> overwrite con {rel_path}.")
                records_by_id[lele_id] = record
                first_path_by_id[lele_id] = md_path
        else:
            records_by_id[lele_id] = record
            first_path_by_id[lele_id] = md_path

        # Riscrivi solo se cambia davvero qualcosa
        if write_missing_frontmatter:
            before = yaml.safe_dump(original_fm, sort_keys=True)
            after = yaml.safe_dump(frontmatter, sort_keys=True)
            if before != after:
                new_content = render_markdown_with_frontmatter(frontmatter, body)
                files_to_update.append((md_path, new_content))

    if files_to_update:
        print(f"[info] Aggiorno {len(files_to_update)} file per aggiungere/sincronizzare il frontmatter.")
        for md_path, new_content in files_to_update:
            md_path.write_text(new_content, encoding="utf-8")

    return records_by_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Importa LeLe da una directory di file .md con frontmatter YAML "
            "e genera un file JSONL compatibile con LeLe Manager."
        )
    )

    parser.add_argument("input_dir", help="Directory radice che contiene le LeLe in formato Markdown.")
    parser.add_argument("output", help="Percorso del file JSONL di output (sarà sovrascritto).")
    parser.add_argument(
        "--on-duplicate",
        choices=["overwrite", "skip", "error"],
        default="overwrite",
        help="Comportamento in caso di ID duplicato (default: overwrite).",
    )
    parser.add_argument(
        "--default-source",
        default="manual",
        help="Valore di default per 'source' se non presente nel frontmatter.",
    )
    parser.add_argument(
        "--default-importance",
        type=int,
        default=3,
        help="Valore di default per 'importance' se non presente nel frontmatter.",
    )
    parser.add_argument(
        "--default-topic",
        default=None,
        help="Topic di default se non presente nel frontmatter (se assente, usa il nome della directory padre).",
    )
    parser.add_argument(
        "--write-missing-frontmatter",
        action="store_true",
        help="Se impostato, aggiunge/sincronizza il frontmatter (id incluso) nei file che ne sono sprovvisti.",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    output_path = Path(args.output).resolve()

    records_by_id = import_from_dir(
        input_dir=input_dir,
        on_duplicate=args.on_duplicate,  # type: ignore[arg-type]
        default_source=args.default_source,
        default_importance=args.default_importance,
        default_topic=args.default_topic,
        write_missing_frontmatter=args.write_missing_frontmatter,
    )

    if not records_by_id:
        print("[info] Nessuna LeLe importata, nessun file scritto.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[info] Scrivo {len(records_by_id)} LeLe in formato JSONL -> {output_path}")
    with output_path.open("w", encoding="utf-8") as f:
        for rec in records_by_id.values():
            line = json.dumps(asdict(rec), ensure_ascii=False, default=str)
            f.write(line + "\n")

    print("[ok] Import completato.")


if __name__ == "__main__":
    main()
