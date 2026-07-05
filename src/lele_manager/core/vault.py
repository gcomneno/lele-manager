from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from lele_manager.cli.import_from_dir import (
    compute_frontmatter_hash,
    derive_id_from_path,
    import_from_dir,
    parse_markdown_with_frontmatter,
    render_markdown_with_frontmatter,
)

ENV_VAULT_DIR = "LELE_VAULT_DIR"
DEFAULT_VAULT_DIRNAME = "LeLeVault"


def resolve_vault_dir() -> Path:
    """Return configured vault directory (may not exist yet)."""
    env = os.environ.get(ENV_VAULT_DIR)
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / DEFAULT_VAULT_DIRNAME).resolve()


def require_vault_dir() -> Path:
    vault = resolve_vault_dir()
    if not vault.is_dir():
        raise FileNotFoundError(
            f"Vault directory not found: {vault} (set {ENV_VAULT_DIR})"
        )
    return vault


@dataclass
class VaultTreeNode:
    type: Literal["dir", "file"]
    name: str
    path: Optional[str] = None
    id: Optional[str] = None
    children: Optional[List["VaultTreeNode"]] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"type": self.type, "name": self.name}
        if self.path is not None:
            out["path"] = self.path
        if self.id is not None:
            out["id"] = self.id
        if self.children is not None:
            out["children"] = [c.to_dict() for c in self.children]
        return out


def build_vault_tree(vault_dir: Path) -> VaultTreeNode:
    """Build a nested tree of directories and markdown lesson files."""

    def walk(current: Path) -> VaultTreeNode:
        children: List[VaultTreeNode] = []
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for entry in entries:
            if entry.is_dir():
                children.append(walk(entry))
            elif entry.suffix.lower() == ".md":
                rel = entry.relative_to(vault_dir).as_posix()
                lesson_id = derive_id_from_path(entry, vault_dir)
                children.append(
                    VaultTreeNode(
                        type="file",
                        name=entry.name,
                        path=rel,
                        id=lesson_id,
                    )
                )
        return VaultTreeNode(
            type="dir",
            name=current.name if current != vault_dir else "",
            children=children,
        )

    return walk(vault_dir)


def find_markdown_by_id(vault_dir: Path, lesson_id: str) -> Optional[Path]:
    """Locate a vault markdown file by frontmatter id or derived path id."""
    target = str(lesson_id)
    for md_path in sorted(vault_dir.rglob("*.md")):
        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        frontmatter, _ = parse_markdown_with_frontmatter(content)
        raw_id = frontmatter.get("id")
        if isinstance(raw_id, str) and raw_id.strip() == target:
            return md_path
        if derive_id_from_path(md_path, vault_dir) == target:
            return md_path
    return None


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "lesson"


def default_relative_path(
    *,
    lesson_id: str,
    topic: str,
    date: str,
    title: Optional[str] = None,
) -> str:
    if "/" in lesson_id:
        return f"{lesson_id}.md"
    slug = _slugify(title or lesson_id)
    return f"{topic}/{date}.{slug}.md"


def build_frontmatter(
    *,
    lesson_id: str,
    topic: str,
    source: str,
    importance: int,
    tags: List[str],
    date: str,
    title: Optional[str],
) -> Dict[str, object]:
    frontmatter: Dict[str, object] = {
        "id": lesson_id,
        "topic": topic,
        "source": source,
        "importance": int(importance),
        "tags": tags,
        "date": date,
    }
    if title:
        frontmatter["title"] = title
    return frontmatter


def write_lesson_markdown(
    vault_dir: Path,
    *,
    lesson_id: str,
    body: str,
    topic: str,
    source: str,
    importance: int,
    tags: List[str],
    date: str,
    title: Optional[str] = None,
    relative_path: Optional[str] = None,
) -> Path:
    """Write or overwrite a lesson markdown file in the vault."""
    vault_dir.mkdir(parents=True, exist_ok=True)

    rel = relative_path or default_relative_path(
        lesson_id=lesson_id,
        topic=topic,
        date=date,
        title=title,
    )
    if not rel.lower().endswith(".md"):
        rel = f"{rel}.md"

    md_path = (vault_dir / rel).resolve()
    vault_root = vault_dir.resolve()
    try:
        md_path.relative_to(vault_root)
    except ValueError as exc:
        raise ValueError(f"Refusing to write outside vault: {md_path}") from exc

    frontmatter = build_frontmatter(
        lesson_id=lesson_id,
        topic=topic,
        source=source,
        importance=importance,
        tags=tags,
        date=date,
        title=title,
    )
    _ = compute_frontmatter_hash(frontmatter)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        render_markdown_with_frontmatter(frontmatter, body.strip()),
        encoding="utf-8",
    )
    return md_path


def import_vault_to_jsonl(
    vault_dir: Path,
    output_path: Path,
    *,
    on_duplicate: str = "overwrite",
    default_source: str = "note",
    default_importance: int = 3,
    write_missing_frontmatter: bool = True,
) -> Dict[str, Any]:
    """Import vault markdown files into a JSONL dataset."""
    records = import_from_dir(
        input_dir=vault_dir,
        on_duplicate=on_duplicate,  # type: ignore[arg-type]
        default_source=default_source,
        default_importance=default_importance,
        default_topic=None,
        write_missing_frontmatter=write_missing_frontmatter,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for rec in records.values():
            f.write(json.dumps(rec.__dict__, ensure_ascii=False, default=str) + "\n")
    topics = sorted({str(r.topic) for r in records.values() if r.topic})
    return {
        "n_lessons": len(records),
        "output_path": str(output_path),
        "topics": topics,
    }


def upsert_jsonl_lesson(
    output_path: Path,
    record: Dict[str, Any],
) -> None:
    """Replace a lesson row by id or append if new."""
    lesson_id = str(record["id"])
    rows: List[Dict[str, Any]] = []
    if output_path.is_file():
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if str(data.get("id")) != lesson_id:
                    rows.append(data)
    rows.append(record)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
