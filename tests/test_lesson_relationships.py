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
    import_from_dir,
    parse_markdown_with_frontmatter,
)
from lele_manager.core.lesson_revision_history import LessonRevisionHistoryStore
from lele_manager.core.vault import (
    import_vault_to_jsonl,
    render_lesson_markdown,
    write_lesson_markdown,
)

from lele_manager.core.relationships import (
    CANONICAL_RELATIONSHIP_TYPES,
    RELATIONSHIP_TYPES,
    RelationshipValidationError,
    normalize_relationships,
    validate_relationship_targets,
)


def test_relationship_vocabulary_keeps_supersedes_public_but_not_generic_canonical() -> None:
    assert RELATIONSHIP_TYPES == (
        "derives-from",
        "corrects",
        "extends",
        "contradicts",
        "supersedes",
        "see-also",
    )
    assert CANONICAL_RELATIONSHIP_TYPES == (
        "derives-from",
        "corrects",
        "extends",
        "contradicts",
        "see-also",
    )


def test_normalize_relationships_accepts_missing_or_empty_metadata() -> None:
    assert normalize_relationships(None, lesson_id="python/source") == {}
    assert normalize_relationships({}, lesson_id="python/source") == {}


def test_normalize_relationships_uses_canonical_type_and_target_order() -> None:
    result = normalize_relationships(
        {
            "see-also": ["z/topic", " a/topic "],
            "extends": ["c/topic", "b/topic"],
            "corrects": [],
        },
        lesson_id="python/source",
    )

    assert list(result) == ["extends", "see-also"]
    assert result == {
        "extends": ("b/topic", "c/topic"),
        "see-also": ("a/topic", "z/topic"),
    }


@pytest.mark.parametrize(
    "value",
    [
        [],
        "see-also",
        42,
    ],
)
def test_normalize_relationships_rejects_non_mapping_metadata(
    value: object,
) -> None:
    with pytest.raises(RelationshipValidationError, match="must be a mapping"):
        normalize_relationships(value, lesson_id="python/source")


def test_normalize_relationships_rejects_unknown_type() -> None:
    with pytest.raises(RelationshipValidationError, match="unknown relationship type"):
        normalize_relationships(
            {"related-to": ["python/target"]},
            lesson_id="python/source",
        )


def test_normalize_relationships_rejects_generic_supersedes_storage() -> None:
    with pytest.raises(
        RelationshipValidationError,
        match="supersedes must use the canonical superseded_by contract",
    ):
        normalize_relationships(
            {"supersedes": ["python/old"]},
            lesson_id="python/new",
        )


def test_normalize_relationships_rejects_non_list_targets() -> None:
    with pytest.raises(RelationshipValidationError, match="must be a list"):
        normalize_relationships(
            {"extends": "python/target"},
            lesson_id="python/source",
        )


@pytest.mark.parametrize("target", [None, 7, "", "   "])
def test_normalize_relationships_rejects_invalid_targets(
    target: object,
) -> None:
    with pytest.raises(RelationshipValidationError):
        normalize_relationships(
            {"extends": [target]},
            lesson_id="python/source",
        )


def test_normalize_relationships_rejects_self_reference() -> None:
    with pytest.raises(RelationshipValidationError, match="lesson itself"):
        normalize_relationships(
            {"see-also": [" python/source "]},
            lesson_id="python/source",
        )


def test_normalize_relationships_rejects_duplicate_target_after_normalization() -> None:
    with pytest.raises(RelationshipValidationError, match="duplicate target"):
        normalize_relationships(
            {"contradicts": ["python/target", " python/target "]},
            lesson_id="python/source",
        )


def test_same_target_may_have_multiple_distinct_relationship_types() -> None:
    assert normalize_relationships(
        {
            "derives-from": ["python/target"],
            "extends": ["python/target"],
        },
        lesson_id="python/source",
    ) == {
        "derives-from": ("python/target",),
        "extends": ("python/target",),
    }


def test_validate_relationship_targets_accepts_exactly_one_match() -> None:
    validate_relationship_targets(
        {
            "extends": ("python/target",),
            "see-also": ("testing/target",),
        },
        resolve_target_count=lambda _target: 1,
    )


def test_validate_relationship_targets_rejects_missing_target() -> None:
    with pytest.raises(RelationshipValidationError, match="does not exist"):
        validate_relationship_targets(
            {"corrects": ("python/missing",)},
            resolve_target_count=lambda _target: 0,
        )


def test_validate_relationship_targets_rejects_ambiguous_target() -> None:
    with pytest.raises(RelationshipValidationError, match="is ambiguous"):
        validate_relationship_targets(
            {"contradicts": ("python/duplicate",)},
            resolve_target_count=lambda _target: 2,
        )

def test_render_relationships_as_portable_canonical_frontmatter() -> None:
    rendered = render_lesson_markdown(
        lesson_id="python/source",
        body="Source knowledge.",
        topic="python",
        source="test",
        importance=3,
        tags=["relationships"],
        date="2026-08-17",
        title="Source",
        relationships={
            "see-also": ["z/topic", "a/topic"],
            "extends": ["c/topic", "b/topic"],
        },
    )

    frontmatter, _ = parse_markdown_with_frontmatter(rendered)

    assert frontmatter["relationships"] == {
        "extends": ["b/topic", "c/topic"],
        "see-also": ["a/topic", "z/topic"],
    }


def test_render_omits_empty_relationships_frontmatter() -> None:
    rendered = render_lesson_markdown(
        lesson_id="python/source",
        body="Source knowledge.",
        topic="python",
        source="test",
        importance=3,
        tags=["relationships"],
        date="2026-08-17",
        title="Source",
        relationships={},
    )

    frontmatter, _ = parse_markdown_with_frontmatter(rendered)

    assert "relationships" not in frontmatter


def test_canonical_snapshot_reads_relationships_from_exact_markdown(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    write_lesson_markdown(
        vault,
        lesson_id="python/source",
        body="Source knowledge.",
        topic="python",
        source="test",
        importance=3,
        tags=["relationships"],
        date="2026-08-17",
        title="Source",
        relationships={
            "see-also": ["python/other"],
            "derives-from": ["python/base"],
        },
    )

    snapshot = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )

    assert snapshot.relationships == {
        "derives-from": ("python/base",),
        "see-also": ("python/other",),
    }


def test_revisioned_edit_preserves_relationships_when_omitted(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    write_lesson_markdown(
        vault,
        lesson_id="python/source",
        body="Before.",
        topic="python",
        source="note",
        importance=3,
        tags=["python"],
        date="2026-08-17",
        title="Source",
        relationships={
            "extends": ["python/base"],
            "see-also": ["python/other"],
        },
    )
    before = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    result = write_revisioned_canonical_lesson_source(
        vault_dir=vault,
        lesson_id="python/source",
        expected_revision=before.canonical_revision,
        history_store=store,
        body="After.",
        topic="python",
        source="note",
        importance=3,
        tags=["python"],
        date="2026-08-17",
        title="Source",
        lifecycle="active",
        superseded_by=None,
        invalidate_cache=lambda: None,
        occurred_at="2026-08-17T13:00:00+00:00",
    )

    after = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )

    assert result.canonical_changed is True
    assert after.relationships == before.relationships
    assert [item.action for item in store.list("python/source")] == [
        "baseline",
        "edit",
    ]


def test_revisioned_semantically_identical_relationship_order_is_noop(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    write_lesson_markdown(
        vault,
        lesson_id="python/source",
        body="Stable.",
        topic="python",
        source="note",
        importance=3,
        tags=["python"],
        date="2026-08-17",
        title="Source",
        relationships={
            "see-also": ["a/topic", "z/topic"],
        },
    )
    before = read_canonical_lesson_snapshot(
        vault_dir=vault,
        lesson_id="python/source",
    )
    store = LessonRevisionHistoryStore(tmp_path / "lesson-revisions.json")

    result = write_revisioned_canonical_lesson_source(
        vault_dir=vault,
        lesson_id="python/source",
        expected_revision=before.canonical_revision,
        history_store=store,
        body="Stable.",
        topic="python",
        source="note",
        importance=3,
        tags=["python"],
        date="2026-08-17",
        title="Source",
        lifecycle="active",
        superseded_by=None,
        relationships={
            "see-also": ("z/topic", "a/topic"),
        },
        invalidate_cache=lambda: None,
        occurred_at="2026-08-17T13:00:00+00:00",
    )

    assert result.canonical_changed is False
    assert result.canonical_revision == before.canonical_revision
    assert store.list("python/source") == ()

def _write_raw_relationship_lesson(
    vault: Path,
    lesson_id: str,
    relationships_yaml: str,
) -> Path:
    path = vault / f"{lesson_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: {lesson_id}\n"
        f"topic: {lesson_id.split('/', 1)[0]}\n"
        "source: test\n"
        "importance: 3\n"
        "tags: [relationships]\n"
        "date: 2026-08-17\n"
        f"title: {lesson_id}\n"
        f"{relationships_yaml}"
        "---\n"
        f"Body for {lesson_id}.\n",
        encoding="utf-8",
    )
    return path


def test_import_normalizes_relationships_into_projection_record(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"

    _write_raw_relationship_lesson(
        vault,
        "python/base",
        "",
    )
    _write_raw_relationship_lesson(
        vault,
        "python/source",
        "relationships:\n"
        "  see-also:\n"
        "    - python/base\n"
        "  extends:\n"
        "    - z/topic\n"
        "    - a/topic\n",
    )

    records = import_from_dir(
        vault,
        "overwrite",
        None,
        None,
        None,
        False,
    )

    assert records["python/source"].relationships == {
        "extends": ["a/topic", "z/topic"],
        "see-also": ["python/base"],
    }


def test_relationships_round_trip_from_markdown_to_jsonl_projection(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    projection = tmp_path / "lessons.jsonl"

    write_lesson_markdown(
        vault,
        lesson_id="python/target",
        body="Target.",
        topic="python",
        source="test",
        importance=3,
        tags=["relationships"],
        date="2026-08-17",
        title="Target",
    )
    write_lesson_markdown(
        vault,
        lesson_id="python/source",
        body="Source.",
        topic="python",
        source="test",
        importance=3,
        tags=["relationships"],
        date="2026-08-17",
        title="Source",
        relationships={
            "see-also": ["python/target"],
            "corrects": ["python/target"],
        },
    )

    import_vault_to_jsonl(vault, projection)

    records = [
        json.loads(line)
        for line in projection.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {record["id"]: record for record in records}

    assert by_id["python/source"]["relationships"] == {
        "corrects": ["python/target"],
        "see-also": ["python/target"],
    }
    assert by_id["python/target"]["relationships"] == {}


def test_import_blocks_structurally_invalid_relationship_metadata(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    source = _write_raw_relationship_lesson(
        vault,
        "python/source",
        "relationships:\n"
        "  extends: python/target\n",
    )
    before = source.read_bytes()

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
        problem.code == "invalid_relationships"
        and problem.field == "relationships"
        and "must be a list" in problem.message
        for problem in plan.validation_problems
    )
    assert source.read_bytes() == before


def test_import_preserves_broken_generic_relationship_for_diagnostics(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"

    _write_raw_relationship_lesson(
        vault,
        "python/source",
        "relationships:\n"
        "  see-also:\n"
        "    - python/missing\n",
    )

    plan = analyze_import_from_dir(
        vault,
        "overwrite",
        None,
        None,
        None,
        False,
    )

    assert plan.blocking is False
    assert plan.candidate_records["python/source"]["relationships"] == {
        "see-also": ["python/missing"],
    }

    records = import_from_dir(
        vault,
        "overwrite",
        None,
        None,
        None,
        False,
    )

    assert records["python/source"].relationships == {
        "see-also": ["python/missing"],
    }

