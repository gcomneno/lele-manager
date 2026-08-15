from __future__ import annotations

import json
from pathlib import Path

import pytest

from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.api import server
from lele_manager.core.lifecycle import LifecycleValidationError
from lele_manager.core.vault_registry import ActiveVaultContext
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

def _context(tmp_path: Path) -> ActiveVaultContext:
    vault = tmp_path / "vault"
    return ActiveVaultContext(
        "test-vault",
        "Test Vault",
        vault,
        tmp_path / "lessons.jsonl",
        tmp_path / "candidates.json",
        tmp_path / "model.joblib",
        "test-vault",
    )


def _write_payload(
    *,
    text: str = "Updated body.",
    lifecycle: object = ...,
    superseded_by: object = ...,
) -> server.LessonVaultWrite:
    values: dict[str, object] = {
        "text": text,
        "topic": "python",
        "source": "test",
        "importance": 3,
        "tags": ["lifecycle"],
        "date": "2026-08-15",
        "title": "Lesson",
    }
    if lifecycle is not ...:
        values["lifecycle"] = lifecycle
    if superseded_by is not ...:
        values["superseded_by"] = superseded_by
    return server.LessonVaultWrite(**values)


def test_update_omission_preserves_existing_lifecycle_metadata(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    write_lesson_markdown(
        context.vault_dir,
        lesson_id="python/replacement",
        body="Replacement.",
        topic="python",
        source="test",
        importance=3,
        tags=[],
        date="2026-08-15",
    )
    original = write_lesson_markdown(
        context.vault_dir,
        lesson_id="python/old",
        body="Old.",
        topic="python",
        source="test",
        importance=3,
        tags=[],
        date="2026-08-15",
        lifecycle="deprecated",
        superseded_by="python/replacement",
    )

    server._write_lesson_to_vault(
        lesson_id="python/old",
        payload=_write_payload(),
        relative_path=original.relative_to(context.vault_dir).as_posix(),
        context=context,
    )

    frontmatter, body = parse_markdown_with_frontmatter(
        original.read_text(encoding="utf-8")
    )
    assert body.strip() == "Updated body."
    assert frontmatter["lifecycle"] == "deprecated"
    assert frontmatter["superseded_by"] == "python/replacement"


def test_explicit_active_and_null_clear_existing_lifecycle_metadata(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    write_lesson_markdown(
        context.vault_dir,
        lesson_id="python/replacement",
        body="Replacement.",
        topic="python",
        source="test",
        importance=3,
        tags=[],
        date="2026-08-15",
    )
    original = write_lesson_markdown(
        context.vault_dir,
        lesson_id="python/old",
        body="Old.",
        topic="python",
        source="test",
        importance=3,
        tags=[],
        date="2026-08-15",
        lifecycle="deprecated",
        superseded_by="python/replacement",
    )

    payload = _write_payload(lifecycle="active", superseded_by=None)
    assert "lifecycle" in payload.model_fields_set
    assert "superseded_by" in payload.model_fields_set

    server._write_lesson_to_vault(
        lesson_id="python/old",
        payload=payload,
        relative_path=original.relative_to(context.vault_dir).as_posix(),
        context=context,
    )

    frontmatter, _ = parse_markdown_with_frontmatter(
        original.read_text(encoding="utf-8")
    )
    assert "lifecycle" not in frontmatter
    assert "superseded_by" not in frontmatter


def test_unknown_supersession_target_fails_without_rewriting_source(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    original = write_lesson_markdown(
        context.vault_dir,
        lesson_id="python/source",
        body="Original.",
        topic="python",
        source="test",
        importance=3,
        tags=[],
        date="2026-08-15",
    )
    before = original.read_bytes()

    with pytest.raises(ValueError, match="does not exist"):
        server._write_lesson_to_vault(
            lesson_id="python/source",
            payload=_write_payload(
                lifecycle="deprecated",
                superseded_by="python/missing",
            ),
            relative_path=original.relative_to(context.vault_dir).as_posix(),
            context=context,
        )

    assert original.read_bytes() == before


def test_supersession_cycle_fails_without_rewriting_source(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    write_lesson_markdown(
        context.vault_dir,
        lesson_id="python/a",
        body="A.",
        topic="python",
        source="test",
        importance=3,
        tags=[],
        date="2026-08-15",
        superseded_by="python/b",
    )
    target = write_lesson_markdown(
        context.vault_dir,
        lesson_id="python/b",
        body="B.",
        topic="python",
        source="test",
        importance=3,
        tags=[],
        date="2026-08-15",
    )
    before = target.read_bytes()

    with pytest.raises(
        LifecycleValidationError,
        match="supersession cycle",
    ):
        server._write_lesson_to_vault(
            lesson_id="python/b",
            payload=_write_payload(
                lifecycle="deprecated",
                superseded_by="python/a",
            ),
            relative_path=target.relative_to(context.vault_dir).as_posix(),
            context=context,
        )

    assert target.read_bytes() == before
