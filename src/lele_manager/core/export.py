from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from lele_manager.cli.import_from_dir import (
    parse_markdown_with_frontmatter,
    render_markdown_with_frontmatter,
)


def _lesson_body(text: str) -> str:
    stripped = (text or "").lstrip()
    if stripped.startswith("---"):
        _, body = parse_markdown_with_frontmatter(text)
        return body.strip()
    return (text or "").strip()


def lesson_to_markdown_block(lesson: Mapping[str, Any], *, include_frontmatter: bool) -> str:
    """Render a single lesson as an Obsidian-friendly markdown block."""
    text = str(lesson.get("text") or "")
    lesson_id = str(lesson.get("id") or "")

    if include_frontmatter:
        if text.lstrip().startswith("---"):
            return text.rstrip() + "\n"

        frontmatter: dict[str, object] = {"id": lesson_id}
        if lesson.get("topic"):
            frontmatter["topic"] = lesson["topic"]
        if lesson.get("source"):
            frontmatter["source"] = lesson["source"]
        if lesson.get("importance") is not None:
            frontmatter["importance"] = int(lesson["importance"])
        tags = lesson.get("tags")
        if isinstance(tags, list) and tags:
            frontmatter["tags"] = [str(t) for t in tags]
        if lesson.get("date"):
            frontmatter["date"] = lesson["date"]
        if lesson.get("title"):
            frontmatter["title"] = lesson["title"]

        return render_markdown_with_frontmatter(frontmatter, _lesson_body(text))

    title = lesson.get("title") or lesson_id
    body = _lesson_body(text)
    return f"## {title}\n\n**id:** `{lesson_id}`\n\n{body}\n"


def search_results_to_markdown(
    results: Sequence[Mapping[str, Any]],
    *,
    include_frontmatter: bool,
    filters_summary: str | None = None,
) -> str:
    """Combine search hits into one markdown document."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header_lines = [
        "# LeLe export",
        "",
        f"_Generated: {generated}_",
        f"_Lessons: {len(results)}_",
    ]
    if filters_summary:
        header_lines.append(f"_Filters: {filters_summary}_")
    header_lines.append("")

    if not results:
        header_lines.append("_Nessuna LeLe corrisponde ai filtri._")
        return "\n".join(header_lines) + "\n"

    blocks = [lesson_to_markdown_block(row, include_frontmatter=include_frontmatter) for row in results]
    return "\n".join(header_lines) + "\n---\n\n".join(blocks) + "\n"
