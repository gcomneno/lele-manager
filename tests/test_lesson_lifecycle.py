from __future__ import annotations

import json
from pathlib import Path

import pytest

from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.core.lifecycle import LifecycleValidationError
from lele_manager.core.vault import (
    import_vault_to_jsonl,
    render_lesson_markdown,
    write_lesson_markdown,
)


def _frontmatter(rendered: str) -> dict[str, object]:
    frontmatter, _ = parse_markdown_with_frontmatter(rendered)
    return frontmatter


def test_active_lifecycle_is_implicit_in_canonical_markdown() -> None:
    rendered = render_lesson_markdown(
        lesson_id="python/active",
        body="Current knowledge.",
        topic="python",
        source="test",
        importance=3,
        tags=["lifecycle"],
        date="2026-08-15",
        title="Active",
    )

    frontmatter = _frontmatter(rendered)
    assert "lifecycle" not in frontmatter
    assert "superseded_by" not in frontmatter


def test_non_active_lifecycle_and_supersession_round_trip_to_projection(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    projection = tmp_path / "lessons.jsonl"

    write_lesson_markdown(
        vault,
        lesson_id="python/replacement",
        body="Replacement knowledge.",
        topic="python",
        source="test",
        importance=4,
        tags=["lifecycle"],
        date="2026-08-15",
        title="Replacement",
    )
    old_path = write_lesson_markdown(
        vault,
        lesson_id="python/old",
        body="Historical knowledge.",
        topic="python",
        source="test",
        importance=2,
        tags=["lifecycle"],
        date="2026-08-14",
        title="Old",
        lifecycle="deprecated",
        superseded_by="python/replacement",
    )

    frontmatter, _ = parse_markdown_with_frontmatter(
        old_path.read_text(encoding="utf-8")
    )
    assert frontmatter["lifecycle"] == "deprecated"
    assert frontmatter["superseded_by"] == "python/replacement"

    import_vault_to_jsonl(vault, projection)

    records = [
        json.loads(line)
        for line in projection.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {record["id"]: record for record in records}

    assert by_id["python/replacement"]["lifecycle"] == "active"
    assert by_id["python/replacement"]["superseded_by"] is None
    assert by_id["python/old"]["lifecycle"] == "deprecated"
    assert by_id["python/old"]["superseded_by"] == "python/replacement"


def test_invalid_lifecycle_fails_closed_before_canonical_write(
    tmp_path: Path,
) -> None:
    with pytest.raises(LifecycleValidationError):
        write_lesson_markdown(
            tmp_path / "vault",
            lesson_id="python/invalid",
            body="Invalid lifecycle.",
            topic="python",
            source="test",
            importance=3,
            tags=[],
            date="2026-08-15",
            lifecycle="obsolete",
        )
