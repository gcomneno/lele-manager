import json
from pathlib import Path

import pytest

from lele_manager.cli.import_from_dir import analyze_import_from_dir


def _analyze(vault: Path, **kwargs: object):
    return analyze_import_from_dir(
        vault,
        kwargs.pop("on_duplicate", "overwrite"),  # type: ignore[arg-type]
        "note",
        3,
        None,
        bool(kwargs.pop("write_missing_frontmatter", False)),
        kwargs.pop("existing_records", ()),  # type: ignore[arg-type]
    )


def _write(vault: Path, name: str, lesson_id: str, body: str = "Body") -> Path:
    path = vault / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {lesson_id}\ntopic: topic\nsource: note\nimportance: 3\n---\n{body}\n",
        encoding="utf-8",
    )
    return path


def test_to_dict_is_json_native_deterministic_and_hides_candidates(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    _write(vault, "z.md", "z")
    _write(vault, "a.md", "a")

    serialized = _analyze(vault).to_dict()

    assert "candidate_records" not in serialized
    assert [change["id"] for change in serialized["changes"]] == ["a", "z"]
    assert json.loads(json.dumps(serialized)) == serialized
    with_candidates = _analyze(vault).to_dict(include_candidate_records=True)
    assert json.loads(json.dumps(with_candidates)) == with_candidates


def test_classifies_complete_record_changes_and_removed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault, "same.md", "same")
    _write(vault, "changed.md", "changed", "new body")
    first = _analyze(vault)
    same = dict(first.candidate_records["same"])
    changed = dict(first.candidate_records["changed"])
    changed["frontmatter_hash"] = "sha256:old"
    old = dict(same)
    old["id"] = "removed"

    plan = _analyze(vault, existing_records=[same, changed, old])
    kinds = {change.lesson_id: change.kind.value for change in plan.changes}

    assert kinds == {"same": "unchanged", "changed": "update", "removed": "removed"}
    assert plan.replace_all is True


def test_create_and_no_total_removal_without_publish(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    plan = _analyze(vault, existing_records=[{"id": "old"}])
    assert plan.replace_all is False
    assert plan.changes == []

    _write(vault, "new.md", "new")
    assert _analyze(vault).changes[0].kind.value == "create"


@pytest.mark.parametrize(
    ("policy", "resolution", "body", "blocking"),
    [
        ("error", "blocked", "first", True),
        ("skip", "kept_first", "first", False),
        ("overwrite", "kept_last", "second", False),
    ],
)
def test_duplicate_policies(
    tmp_path: Path, policy: str, resolution: str, body: str, blocking: bool
) -> None:
    vault = tmp_path / "vault"
    _write(vault, "a.md", "dup", "first")
    _write(vault, "b.md", "dup", "second")

    plan = _analyze(vault, on_duplicate=policy)

    assert plan.duplicates[0].resolution.value == resolution
    assert plan.candidate_records["dup"]["text"] == body
    assert plan.blocking is blocking


def test_ignored_file_pending_write_and_analysis_has_no_side_effects(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    markdown = vault / "topic" / "2025-01-01.lesson.md"
    markdown.parent.mkdir(parents=True)
    markdown.write_text("Body\n", encoding="utf-8")
    ignored = vault / "notes.txt"
    ignored.write_text("ignored", encoding="utf-8")
    (vault / "empty-directory").mkdir()
    original = markdown.read_bytes()

    plan = _analyze(vault, write_missing_frontmatter=True)

    assert [(item.path, item.reason) for item in plan.ignored_files] == [
        ("notes.txt", "not_markdown")
    ]
    assert [(item.path, item.reason) for item in plan.pending_source_writes] == [
        ("topic/2025-01-01.lesson.md", "complete_frontmatter")
    ]
    assert markdown.read_bytes() == original


def test_malformed_yaml_is_non_blocking(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "bad.md").write_text("---\nid: [broken\n---\nBody\n", encoding="utf-8")

    plan = _analyze(vault)

    assert [
        (problem.code, problem.blocking) for problem in plan.validation_problems
    ] == [("malformed_yaml", False)]
    assert "bad" in plan.candidate_records

def test_imports_markdown_extension_case_insensitively(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault, "LEZIONE.MD", "uppercase")

    plan = _analyze(vault)

    assert sorted(plan.candidate_records) == ["uppercase"]
    assert plan.ignored_files == []
    assert [
        (change.lesson_id, change.kind.value)
        for change in plan.changes
    ] == [("uppercase", "create")]
    assert plan.replace_all is True
