from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import sys
import yaml

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from lele_manager.composition import projection_store
from lele_manager.core.import_plan import (
    DuplicateId,
    DuplicatePolicy as PlanDuplicatePolicy,
    DuplicateResolution,
    IgnoredFile,
    ImportPlan,
    LessonChange,
    LessonChangeKind,
    PendingSourceWrite,
    ValidationProblem,
)
from lele_manager.core.json_compat import json_native
from lele_manager.core.projection_store import ProjectionStoreError

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
        return {}, content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip().startswith("---"):
            end_idx = i
            break

    if end_idx is None:
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
    fm_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).rstrip()
    return f"---\n{fm_text}\n---\n\n{body.rstrip()}\n"


# ---------------------------------------------------------------------------
# Helper per ID, topic, hash
# ---------------------------------------------------------------------------
def derive_id_from_path(md_path: Path, root_dir: Path) -> str:
    rel = md_path.relative_to(root_dir).as_posix()
    if rel.lower().endswith(".md"):
        rel = rel[:-3]
    return rel


def derive_topic(
    frontmatter: Dict[str, object], md_path: Path, default_topic: Optional[str]
) -> Optional[str]:
    if "topic" in frontmatter and isinstance(frontmatter["topic"], str):
        t = frontmatter["topic"].strip()
        if t:
            return t
    if default_topic:
        return default_topic
    parent = md_path.parent.name
    return parent or None


def normalize_tags(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    txt = str(value)
    if "," in txt:
        return [part.strip() for part in txt.split(",") if part.strip()]
    return [txt.strip()] if txt.strip() else []


def _normalize_importance(
    value: object,
    default: Optional[int],
) -> Tuple[Optional[int], bool]:
    if isinstance(value, (str, bytes, bytearray, int, float)):
        try:
            return int(value), False
        except (TypeError, ValueError):
            pass
    return default, True


def _normalize_frontmatter_date(value: object) -> Optional[str]:
    """
    Normalizza 'date' dal frontmatter:
    - str -> strip
    - datetime/date -> YYYY-MM-DD
    - altro -> None
    """
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    return None


def derive_date(frontmatter: Dict[str, object], md_path: Path) -> Optional[str]:
    if "date" in frontmatter:
        norm = _normalize_frontmatter_date(frontmatter.get("date"))
        if norm:
            return norm

    stem = md_path.stem
    parts = stem.split(".")
    if parts and len(parts[0]) == 10 and parts[0].count("-") == 2:
        return parts[0]
    return None


def compute_frontmatter_hash(frontmatter: Dict[str, object]) -> str:
    text = yaml.safe_dump(frontmatter, sort_keys=True)
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{h}"


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------
def _markdown_files(input_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".md"
    )


def analyze_import_from_dir(
    input_dir: Path,
    on_duplicate: DuplicatePolicy,
    default_source: Optional[str],
    default_importance: Optional[int],
    default_topic: Optional[str],
    write_missing_frontmatter: bool,
    existing_records: Sequence[Mapping[str, Any]] = (),
) -> ImportPlan:
    if not input_dir.is_dir():
        raise SystemExit(f"[errore] Directory di input non trovata: {input_dir}")

    records_by_id: Dict[str, LeLeRecord] = {}
    first_path_by_id: Dict[str, Path] = {}
    pending_source_by_id: dict[str, tuple[PendingSourceWrite, str] | None] = {}
    plan = ImportPlan()

    for path in sorted(input_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() != ".md":
            plan.ignored_files.append(
                IgnoredFile(path.relative_to(input_dir).as_posix(), "not_markdown")
            )

    md_files = _markdown_files(input_dir)
    if not md_files:
        return plan

    for md_path in md_files:
        rel_path = md_path.relative_to(input_dir).as_posix()

        try:
            content = md_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            plan.validation_problems.append(
                ValidationProblem(
                    code="invalid_utf8",
                    message="Impossibile leggere il file come UTF-8.",
                    path=rel_path,
                )
            )
            continue

        source_frontmatter, body = parse_markdown_with_frontmatter(content)
        if _has_malformed_yaml_frontmatter(content):
            plan.validation_problems.append(
                ValidationProblem(
                    code="malformed_yaml",
                    message="Frontmatter YAML malformato; trattato come assente.",
                    path=rel_path,
                )
            )
        frontmatter = dict(source_frontmatter)
        source_frontmatter_changed = False

        # ID
        raw_id = frontmatter.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            lele_id = raw_id.strip()
        else:
            lele_id = derive_id_from_path(md_path, input_dir)
            frontmatter["id"] = lele_id
            if write_missing_frontmatter:
                source_frontmatter["id"] = lele_id
                source_frontmatter_changed = True

        # topic
        topic = derive_topic(frontmatter, md_path, default_topic)
        raw_topic = frontmatter.get("topic")
        if topic is not None and not (isinstance(raw_topic, str) and raw_topic.strip()):
            frontmatter["topic"] = topic
            if write_missing_frontmatter:
                source_frontmatter["topic"] = topic
                source_frontmatter_changed = True

        # source
        source: Optional[str]
        raw_source = frontmatter.get("source")
        if isinstance(raw_source, str) and raw_source.strip():
            source = raw_source.strip()
        else:
            source = default_source
            if default_source is not None:
                frontmatter["source"] = default_source
                if write_missing_frontmatter:
                    source_frontmatter["source"] = default_source
                    source_frontmatter_changed = True

        # importance
        if "importance" in frontmatter:
            importance, used_default_importance = _normalize_importance(
                frontmatter["importance"],
                default_importance,
            )
            if used_default_importance and default_importance is not None:
                frontmatter["importance"] = int(default_importance)
                if write_missing_frontmatter:
                    source_frontmatter["importance"] = int(default_importance)
                    source_frontmatter_changed = True
        else:
            importance = default_importance
            if default_importance is not None:
                frontmatter["importance"] = int(default_importance)
                if write_missing_frontmatter:
                    source_frontmatter["importance"] = int(default_importance)
                    source_frontmatter_changed = True

        # tags
        tags = normalize_tags(frontmatter.get("tags"))

        # date (normalizzata)
        date = derive_date(frontmatter, md_path)
        normalized_date = _normalize_frontmatter_date(frontmatter.get("date"))
        if normalized_date is not None:
            frontmatter["date"] = normalized_date
        elif date is not None:
            frontmatter["date"] = date
            if write_missing_frontmatter:
                source_frontmatter["date"] = date
                source_frontmatter_changed = True

        # title
        title = None
        if "title" in frontmatter and isinstance(frontmatter["title"], str):
            title = frontmatter["title"].strip() or None

        frontmatter_hash = compute_frontmatter_hash(frontmatter)
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
            msg = f"ID duplicato '{lele_id}' in {rel_path} (già visto in {existing_path.relative_to(input_dir)})"

            if on_duplicate == "error":
                resolution = DuplicateResolution.BLOCKED
                plan.validation_problems.append(
                    ValidationProblem(
                        code="duplicate_id",
                        message=msg,
                        path=rel_path,
                        field="id",
                        blocking=True,
                    )
                )
                plan.duplicates.append(
                    DuplicateId(
                        lele_id,
                        existing_path.relative_to(input_dir).as_posix(),
                        rel_path,
                        PlanDuplicatePolicy.ERROR,
                        resolution,
                    )
                )
                continue
            if on_duplicate == "skip":
                plan.duplicates.append(
                    DuplicateId(
                        lele_id,
                        existing_path.relative_to(input_dir).as_posix(),
                        rel_path,
                        PlanDuplicatePolicy.SKIP,
                        DuplicateResolution.KEPT_FIRST,
                    )
                )
                continue
            if on_duplicate == "overwrite":
                plan.duplicates.append(
                    DuplicateId(
                        lele_id,
                        existing_path.relative_to(input_dir).as_posix(),
                        rel_path,
                        PlanDuplicatePolicy.OVERWRITE,
                        DuplicateResolution.KEPT_LAST,
                    )
                )

        pending_source: tuple[PendingSourceWrite, str] | None = None
        if write_missing_frontmatter and source_frontmatter_changed:
            new_content = render_markdown_with_frontmatter(source_frontmatter, body)
            pending_source = (
                PendingSourceWrite(rel_path, "complete_frontmatter"),
                new_content,
            )

        records_by_id[lele_id] = record
        first_path_by_id[lele_id] = md_path
        pending_source_by_id[lele_id] = pending_source

    if not plan.blocking:
        for lesson_id in sorted(pending_source_by_id):
            pending = pending_source_by_id[lesson_id]
            if pending is not None:
                source_write, content = pending
                plan.pending_source_writes.append(source_write)
                plan.pending_source_contents[source_write.path] = content

    plan.candidate_records = {
        lesson_id: asdict(record) for lesson_id, record in records_by_id.items()
    }
    plan.replace_all = bool(records_by_id) and not plan.blocking
    existing_by_id = {
        str(record["id"]): record for record in existing_records if "id" in record
    }
    for lesson_id, record in records_by_id.items():
        candidate = asdict(record)
        existing = existing_by_id.get(lesson_id)
        if existing is None:
            kind = LessonChangeKind.CREATE
        elif json_native(existing) == json_native(candidate):
            kind = LessonChangeKind.UNCHANGED
        else:
            kind = LessonChangeKind.UPDATE
        plan.changes.append(LessonChange(lesson_id, kind, record.path))
    if plan.replace_all:
        for lesson_id in existing_by_id.keys() - records_by_id.keys():
            plan.changes.append(LessonChange(lesson_id, LessonChangeKind.REMOVED))
    return plan


def _has_malformed_yaml_frontmatter(content: str) -> bool:
    lines = content.splitlines()
    if not lines or not lines[0].strip().startswith("---"):
        return False
    for index in range(1, len(lines)):
        if lines[index].strip().startswith("---"):
            try:
                return not isinstance(
                    yaml.safe_load("\n".join(lines[1:index])) or {}, dict
                )
            except yaml.YAMLError:
                return True
    return False


def import_from_dir(
    input_dir: Path,
    on_duplicate: DuplicatePolicy,
    default_source: Optional[str],
    default_importance: Optional[int],
    default_topic: Optional[str],
    write_missing_frontmatter: bool,
) -> Dict[str, LeLeRecord]:
    plan = analyze_import_from_dir(
        input_dir,
        on_duplicate,
        default_source,
        default_importance,
        default_topic,
        write_missing_frontmatter,
    )
    md_files = _markdown_files(input_dir)
    if not md_files:
        print(f"[warn] Nessun file .md trovato sotto {input_dir}")
        return {}
    print(f"[info] Trovati {len(md_files)} file .md sotto {input_dir}")
    for duplicate in plan.duplicates:
        msg = (
            f"ID duplicato '{duplicate.lesson_id}' in {duplicate.duplicate_path} "
            f"(già visto in {duplicate.first_path})"
        )
        if duplicate.policy is PlanDuplicatePolicy.ERROR:
            raise SystemExit(f"[errore] {msg}")
        if duplicate.policy is PlanDuplicatePolicy.SKIP:
            print(f"[warn] {msg} -> skip nuovo file.")
        else:
            print(f"[info] {msg} -> overwrite con {duplicate.duplicate_path}.")
    for problem in plan.validation_problems:
        if problem.code == "invalid_utf8":
            print(f"[warn] Impossibile leggere {problem.path} come UTF-8, salto.")
    if plan.pending_source_writes:
        print(
            f"[info] Aggiorno {len(plan.pending_source_writes)} file per "
            "aggiungere/sincronizzare il frontmatter."
        )
        for pending in plan.pending_source_writes:
            (input_dir / pending.path).write_text(
                plan.pending_source_contents[pending.path], encoding="utf-8"
            )
    return {
        lesson_id: LeLeRecord(**dict(record))
        for lesson_id, record in plan.candidate_records.items()
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def render_import_plan(plan: ImportPlan) -> str:
    """Render a stable, human-readable dry-run report."""
    changes_by_kind = {
        kind: sorted(
            (change for change in plan.changes if change.kind is kind),
            key=lambda change: (change.lesson_id, change.path or ""),
        )
        for kind in LessonChangeKind
    }
    lines = [
        "Piano import (dry-run)",
        "Riepilogo: "
        + ", ".join(
            f"{kind.value}={len(changes_by_kind[kind])}"
            for kind in LessonChangeKind
        )
        + f", duplicati={len(plan.duplicates)}"
        + f", problemi={len(plan.validation_problems)}"
        + f", file ignorati={len(plan.ignored_files)}"
        + f", scritture sorgenti={len(plan.pending_source_writes)}",
    ]

    for kind in LessonChangeKind:
        lines.append(f"{kind.value}:")
        changes = changes_by_kind[kind]
        if not changes:
            lines.append("  (nessuno)")
        for change in changes:
            location = f" — {change.path}" if change.path else ""
            lines.append(f"  - {change.lesson_id}{location}")

    lines.append("duplicate IDs:")
    if not plan.duplicates:
        lines.append("  (nessuno)")
    for duplicate in sorted(
        plan.duplicates,
        key=lambda item: (item.lesson_id, item.first_path, item.duplicate_path),
    ):
        lines.append(
            f"  - {duplicate.lesson_id}: {duplicate.first_path} / "
            f"{duplicate.duplicate_path}; policy={duplicate.policy.value}; "
            f"risoluzione={duplicate.resolution.value}"
        )

    lines.append("validation problems:")
    if not plan.validation_problems:
        lines.append("  (nessuno)")
    for problem in sorted(
        plan.validation_problems,
        key=lambda item: (item.path or "", item.code, item.field or "", item.message),
    ):
        severity = "bloccante" if problem.blocking else "non bloccante"
        location = f" — {problem.path}" if problem.path else ""
        field = f"; campo={problem.field}" if problem.field else ""
        lines.append(
            f"  - [{severity}] {problem.code}{location}{field}: {problem.message}"
        )

    lines.append("ignored files:")
    if not plan.ignored_files:
        lines.append("  (nessuno)")
    for ignored in sorted(plan.ignored_files, key=lambda item: (item.path, item.reason)):
        lines.append(f"  - {ignored.path}: {ignored.reason}")

    lines.append("pending source writes:")
    if not plan.pending_source_writes:
        lines.append("  (nessuna)")
    for pending in sorted(
        plan.pending_source_writes, key=lambda item: (item.path, item.reason)
    ):
        lines.append(f"  - {pending.path}: {pending.reason}")

    if plan.replace_all:
        lines.append("Pubblicazione replace-all: avverrebbe.")
    else:
        lines.append("Pubblicazione replace-all: non avverrebbe.")
    lines.append("Nessuna modifica applicata.")
    return "\n".join(lines)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Importa LeLe da una directory di file .md con frontmatter YAML "
            "e genera un file JSONL compatibile con LeLe Manager."
        )
    )
    parser.add_argument(
        "input_dir", help="Directory radice che contiene le LeLe in formato Markdown."
    )
    parser.add_argument(
        "output", help="Percorso del file JSONL di output (sarà sovrascritto)."
    )
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
        help=(
            "Completa o ripara i campi mancanti/non validi del frontmatter sorgente; "
            "i file già validi non vengono riscritti."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analizza e mostra le modifiche senza applicare alcuna scrittura.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    output_path = Path(args.output).resolve()

    if args.dry_run:
        if not input_dir.is_dir():
            print(
                f"[errore] Directory di input non trovata: {input_dir}",
                file=sys.stderr,
            )
            raise SystemExit(2)

        store = projection_store(output_path)
        try:
            existing_records = store.snapshot().list()
        except (ProjectionStoreError, OSError) as exc:
            print(
                f"[errore] Output corrente non valido o non leggibile: {exc}",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        plan = analyze_import_from_dir(
            input_dir=input_dir,
            on_duplicate=args.on_duplicate,
            default_source=args.default_source,
            default_importance=args.default_importance,
            default_topic=args.default_topic,
            write_missing_frontmatter=args.write_missing_frontmatter,
            existing_records=existing_records,
        )
        print(render_import_plan(plan))
        if plan.blocking:
            raise SystemExit(1)
        return

    records_by_id = import_from_dir(
        input_dir=input_dir,
        on_duplicate=args.on_duplicate,
        default_source=args.default_source,
        default_importance=args.default_importance,
        default_topic=args.default_topic,
        write_missing_frontmatter=args.write_missing_frontmatter,
    )

    if not records_by_id:
        print("[info] Nessuna LeLe importata, nessun file scritto.")
        return

    print(f"[info] Scrivo {len(records_by_id)} LeLe in formato JSONL -> {output_path}")
    projection_store(output_path).publish(
        [asdict(record) for record in records_by_id.values()]
    )

    print("[ok] Import completato.")


if __name__ == "__main__":
    main()
