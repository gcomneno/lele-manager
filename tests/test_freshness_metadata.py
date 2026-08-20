from __future__ import annotations

import json
from pathlib import Path

import pytest

from lele_manager.application.lesson_writing import (
    read_canonical_lesson_snapshot,
    write_revisioned_canonical_lesson_source,
)
from lele_manager.cli.import_from_dir import (
    analyze_import_from_dir,
    parse_markdown_with_frontmatter,
)
from lele_manager.core.lesson_revision_history import LessonRevisionHistoryStore
from lele_manager.core.vault import (
    import_vault_to_jsonl,
    render_lesson_markdown,
    write_lesson_markdown,
)


def _lesson_kwargs() -> dict[str, object]:
    return {
        "lesson_id": "python/source",
        "body": "Freshness metadata.",
        "topic": "python",
        "source": "test",
        "importance": 4,
        "tags": ["freshness"],
        "date": "2026-01-01",
        "title": "Freshness source",
    }


def test_render_review_metadata_as_portable_canonical_frontmatter() -> None:
    rendered = render_lesson_markdown(
        **_lesson_kwargs(),
        reviewed_at="2026-08-01",
        review_interval_days=180,
    )

    frontmatter, _ = parse_markdown_with_frontmatter(rendered)

    assert str(frontmatter["reviewed_at"]) == "2026-08-01"
    assert frontmatter["review_interval_days"] == 180


def test_render_omits_absent_review_metadata() -> None:
    rendered = render_lesson_markdown(**_lesson_kwargs())

    frontmatter, _ = parse_markdown_with_frontmatter(rendered)

    assert "reviewed_at" not in frontmatter
    assert "review_interval_days" not in frontmatter


def test_snapshot_reads_canonical_review_metadata(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write_lesson_markdown(
        vault,
        **_lesson_kwargs(),
        reviewed_at="2026-08-01",
        review_interval_days=90,
    )

    snapshot = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )

    assert snapshot.reviewed_at == "2026-08-01"
    assert snapshot.review_interval_days == 90


def test_revisioned_edit_preserves_review_metadata_when_omitted(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    write_lesson_markdown(
        vault,
        **_lesson_kwargs(),
        reviewed_at="2026-08-01",
        review_interval_days=180,
    )
    before = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )
    history = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    result = write_revisioned_canonical_lesson_source(
        vault_dir=vault,
        lesson_id="python/source",
        expected_revision=before.canonical_revision,
        history_store=history,
        body="Edited body.",
        topic="python",
        source="test",
        importance=4,
        tags=["freshness"],
        date="2026-01-01",
        title="Freshness source",
        lifecycle="active",
        superseded_by=None,
        invalidate_cache=lambda: None,
    )

    after = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )

    assert result.canonical_changed is True
    assert after.reviewed_at == "2026-08-01"
    assert after.review_interval_days == 180


def test_revisioned_edit_can_explicitly_clear_review_metadata(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    path = write_lesson_markdown(
        vault,
        **_lesson_kwargs(),
        reviewed_at="2026-08-01",
        review_interval_days=180,
    )
    before = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )
    history = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    result = write_revisioned_canonical_lesson_source(
        vault_dir=vault,
        lesson_id="python/source",
        expected_revision=before.canonical_revision,
        history_store=history,
        body=before.text,
        topic=before.topic or "python",
        source=before.source or "test",
        importance=before.importance or 4,
        tags=before.tags,
        date=before.date or "2026-01-01",
        title=before.title,
        lifecycle=before.lifecycle,
        superseded_by=before.superseded_by,
        reviewed_at=None,
        review_interval_days=None,
        invalidate_cache=lambda: None,
    )

    frontmatter, _ = parse_markdown_with_frontmatter(
        path.read_text(encoding="utf-8")
    )

    assert result.canonical_changed is True
    assert "reviewed_at" not in frontmatter
    assert "review_interval_days" not in frontmatter


def test_review_metadata_round_trips_into_projection(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    projection = tmp_path / "lessons.jsonl"

    write_lesson_markdown(
        vault,
        **_lesson_kwargs(),
        reviewed_at="2026-08-01",
        review_interval_days=120,
    )

    import_vault_to_jsonl(vault, projection)

    records = [
        json.loads(line)
        for line in projection.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(records) == 1
    assert records[0]["reviewed_at"] == "2026-08-01"
    assert records[0]["review_interval_days"] == 120


@pytest.mark.parametrize(
    ("metadata", "code", "field"),
    [
        ("reviewed_at: not-a-date\n", "invalid_reviewed_at", "reviewed_at"),
        (
            "review_interval_days: 0\n",
            "invalid_review_interval_days",
            "review_interval_days",
        ),
        (
            "review_interval_days: 3651\n",
            "invalid_review_interval_days",
            "review_interval_days",
        ),
    ],
)
def test_import_blocks_invalid_review_metadata_without_mutating_source(
    tmp_path: Path,
    metadata: str,
    code: str,
    field: str,
) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "source.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\n"
        "id: python/source\n"
        "topic: python\n"
        "source: test\n"
        "importance: 4\n"
        "tags: [freshness]\n"
        "date: 2026-01-01\n"
        f"{metadata}"
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    before = path.read_bytes()

    plan = analyze_import_from_dir(
        vault,
        "overwrite",
        None,
        None,
        None,
        False,
    )

    assert plan.blocking is True
    assert any(
        problem.code == code
        and problem.field == field
        and problem.blocking
        for problem in plan.validation_problems
    )
    assert path.read_bytes() == before
