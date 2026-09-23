from __future__ import annotations

from collections.abc import Sequence

from lele_manager.application.lesson_writing import CanonicalLessonSnapshot
from lele_manager.core.relationships import CanonicalRelationshipType


_RELATIONSHIP_ORDER: tuple[CanonicalRelationshipType, ...] = (
    "derives-from",
    "corrects",
    "extends",
    "contradicts",
    "see-also",
)


def _render_tags(tags: Sequence[str]) -> str | None:
    if not tags:
        return None
    return ", ".join(f"`{tag}`" for tag in tags)


def _render_relationships(
    lesson: CanonicalLessonSnapshot,
) -> list[str]:
    lines: list[str] = []

    for relation_type in _RELATIONSHIP_ORDER:
        targets = lesson.relationships.get(relation_type, ())
        for target in targets:
            lines.append(f"- {relation_type} → `{target}`")

    return lines


def _render_lesson(
    lesson: CanonicalLessonSnapshot,
) -> str:
    title = lesson.title or lesson.lesson_id

    lines = [
        f"## {title}",
        "",
        f"ID: `{lesson.lesson_id}`",
        f"Lifecycle: `{lesson.lifecycle}`",
    ]

    if lesson.topic:
        lines.append(f"Topic: `{lesson.topic}`")

    rendered_tags = _render_tags(lesson.tags)
    if rendered_tags:
        lines.append(f"Tags: {rendered_tags}")

    if lesson.superseded_by:
        lines.append(
            f"Superseded by: `{lesson.superseded_by}`"
        )

    lines.extend(
        [
            "",
            lesson.text.strip(),
        ]
    )

    relationship_lines = _render_relationships(lesson)
    if relationship_lines:
        lines.extend(
            [
                "",
                "Relationships:",
                *relationship_lines,
            ]
        )

    return "\n".join(lines).rstrip()


def render_assistant_context(
    lessons: Sequence[CanonicalLessonSnapshot],
) -> str:
    """Render deterministic assistant-ready context from canonical lessons.

    The renderer intentionally excludes runtime, projection, model, ranking,
    diagnostic, path, and revision-fingerprint state. Input order is preserved.
    """

    header = [
        "# LeLe Assistant Context",
        "",
        f"Scope: {len(lessons)} LeLe",
        "",
    ]

    if not lessons:
        return "\n".join(
            [
                *header,
                "No LeLe selected.",
                "",
            ]
        )

    blocks = [_render_lesson(lesson) for lesson in lessons]

    return "\n".join(header) + "\n---\n\n".join(blocks) + "\n"
