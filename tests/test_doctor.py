from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest

from lele_manager.cli import lele as lele_cli
from lele_manager.core.doctor import (
    DoctorOperationalError,
    check_markdown_files,
    parse_markdown_diagnostic,
)


def lesson_text(
    lesson_id: str,
    *,
    topic: str = "python",
    source: str = "note",
    importance: object = 3,
    tags: object = None,
    date: str = "2026-07-13",
    title: str = "Una lesson",
    body: str = "Contenuto utile.",
) -> str:
    if tags is None:
        tags = ["python", "test"]
    tags_yaml = json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else str(tags)
    return textwrap.dedent(
        f"""\
        ---
        id: {lesson_id}
        topic: {topic}
        source: {source}
        importance: {importance}
        tags: {tags_yaml}
        date: {date}
        title: {title}
        ---

        {body}
        """
    )


def write_valid(vault: Path, relative: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        lesson_text(Path(relative).with_suffix("").as_posix(), topic=Path(relative).parts[0]),
        encoding="utf-8",
    )
    return path


def problem_codes(path: Path, vault: Path) -> set[str]:
    report = check_markdown_files([path], vault_dir=vault)
    return {problem.code for problem in report.problems}


def run_cli(argv: list[str]) -> int:
    with pytest.raises(SystemExit) as exc_info:
        lele_cli.main(argv)
    assert isinstance(exc_info.value.code, int)
    return exc_info.value.code


def test_completely_valid_lesson_passes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = write_valid(vault, "python/2026-07-13.valid.md")

    report = check_markdown_files([path], vault_dir=vault)

    assert report.valid
    assert report.files_checked == 1
    assert report.unique_ids == 1
    assert report.problems == ()


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        ("Solo body.\n", "missing_frontmatter"),
        ("---\nid: broken\n", "unclosed_frontmatter"),
        ("---\nid: [broken\n---\nBody\n", "invalid_yaml"),
        ("---\n- one\n- two\n---\nBody\n", "frontmatter_not_mapping"),
    ],
)
def test_frontmatter_diagnostics(
    tmp_path: Path, content: str, expected_code: str
) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "broken.md"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")

    assert expected_code in problem_codes(path, vault)


def test_valid_but_empty_yaml_frontmatter_is_distinct_from_parse_errors(
    tmp_path: Path,
) -> None:
    content = "---\n---\nBody presente.\n"
    parsed = parse_markdown_diagnostic(content)
    vault = tmp_path / "vault"
    path = vault / "python" / "empty-frontmatter.md"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")

    report = check_markdown_files([path], vault_dir=vault)

    assert parsed.problem is None
    assert parsed.frontmatter == {}
    assert {problem.code for problem in report.problems} == {"missing_field"}
    assert {problem.field for problem in report.problems} == {
        "id",
        "topic",
        "source",
        "importance",
        "tags",
        "date",
        "title",
    }


def test_missing_required_field(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = write_valid(vault, "python/missing.md")
    path.write_text(path.read_text(encoding="utf-8").replace("source: note\n", ""), encoding="utf-8")

    report = check_markdown_files([path], vault_dir=vault)

    assert any(p.code == "missing_field" and p.field == "source" for p in report.problems)


@pytest.mark.parametrize("field", ["id", "topic", "source", "title"])
def test_required_string_must_be_non_empty(tmp_path: Path, field: str) -> None:
    vault = tmp_path / "vault"
    path = write_valid(vault, "python/empty.md")
    content = path.read_text(encoding="utf-8")
    content = content.replace(f"{field}: {('python/empty' if field == 'id' else 'python' if field == 'topic' else 'note' if field == 'source' else 'Una lesson')}\n", f"{field}: '   '\n")
    path.write_text(content, encoding="utf-8")

    report = check_markdown_files([path], vault_dir=vault)

    assert any(p.code == "invalid_non_empty_string" and p.field == field for p in report.problems)


@pytest.mark.parametrize(
    ("importance", "expected_code"),
    [("high", "invalid_importance_type"), (0, "importance_out_of_range"), (6, "importance_out_of_range")],
)
def test_invalid_importance(tmp_path: Path, importance: object, expected_code: str) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "importance.md"
    path.parent.mkdir(parents=True)
    path.write_text(lesson_text("python/importance", importance=importance), encoding="utf-8")

    assert expected_code in problem_codes(path, vault)


@pytest.mark.parametrize(
    ("tags", "expected_code"),
    [("python", "invalid_tags_type"), ([], "invalid_tags"), (["python", ""], "invalid_tag"), (["python", 3], "invalid_tag")],
)
def test_invalid_tags(tmp_path: Path, tags: object, expected_code: str) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "tags.md"
    path.parent.mkdir(parents=True)
    path.write_text(lesson_text("python/tags", tags=tags), encoding="utf-8")

    assert expected_code in problem_codes(path, vault)


@pytest.mark.parametrize("date", ["13-07-2026", "2026-02-30"])
def test_date_must_be_iso_and_real(tmp_path: Path, date: str) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "date.md"
    path.parent.mkdir(parents=True)
    path.write_text(lesson_text("python/date", date=date), encoding="utf-8")

    assert "invalid_date" in problem_codes(path, vault)


def test_body_must_not_be_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "empty-body.md"
    path.parent.mkdir(parents=True)
    path.write_text(lesson_text("python/empty-body", body="   "), encoding="utf-8")

    assert "empty_body" in problem_codes(path, vault)


def test_topic_and_id_must_match_vault_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "actual.md"
    path.parent.mkdir(parents=True)
    path.write_text(lesson_text("other/wrong", topic="other"), encoding="utf-8")

    codes = problem_codes(path, vault)

    assert "topic_path_mismatch" in codes
    assert "id_path_mismatch" in codes


def test_duplicate_id_is_found_in_whole_vault_for_selected_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    selected = write_valid(vault, "python/selected.md")
    duplicate = vault / "other" / "duplicate.md"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text(lesson_text("python/selected", topic="other"), encoding="utf-8")

    report = check_markdown_files([selected], vault_dir=vault)

    duplicate_problem = next(problem for problem in report.problems if problem.code == "duplicate_id")
    assert "python/selected.md" in duplicate_problem.message
    assert "other/duplicate.md" in duplicate_problem.message
    assert report.files_checked == 1


def test_non_utf8_is_a_validation_problem(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "python" / "binary.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe")

    assert "invalid_utf8" in problem_codes(path, vault)


def test_cli_multiple_explicit_files_and_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    first = write_valid(vault, "python/first.md")
    second = write_valid(vault, "linux/second.md")
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))

    code = run_cli(["doctor", str(second), str(first)])

    output = capsys.readouterr()
    assert code == 0
    assert output.err == ""
    assert "[ok] linux/second.md" in output.out
    assert "[ok] python/first.md" in output.out
    assert "File controllati: 2" in output.out


def test_cli_scans_vault_recursively_and_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "vault"
    write_valid(vault, "python/good.md")
    broken = vault / "nested" / "deeper" / "bad.md"
    broken.parent.mkdir(parents=True)
    broken.write_text("No frontmatter\n", encoding="utf-8")
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))

    code = run_cli(["doctor"])

    output = capsys.readouterr()
    assert code == 1
    assert output.err == ""
    assert "nested/deeper/bad.md" in output.out
    assert "File controllati: 2" in output.out


def test_cli_json_is_stable_and_contains_no_human_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    write_valid(vault, "python/valid.md")

    code = run_cli(["doctor", "--vault", str(vault), "--json"])

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert code == 0
    assert output.err == ""
    assert payload == {
        "valid": True,
        "files_checked": 1,
        "checked_files": ["python/valid.md"],
        "unique_ids": 1,
        "error_count": 0,
        "problems": [],
    }


def test_cli_returns_two_for_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.md"

    code = run_cli(["doctor", str(missing)])

    output = capsys.readouterr()
    assert code == 2
    assert output.out == ""
    assert "path non trovato" in output.err


def test_explicit_file_outside_vault_is_an_operational_error(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    external = tmp_path / "external.md"
    external.write_text(lesson_text("external"), encoding="utf-8")

    with pytest.raises(DoctorOperationalError, match="fuori dalla radice del vault"):
        check_markdown_files([external], vault_dir=vault)


def test_explicit_file_without_vault_context_uses_local_validation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "standalone.md"
    path.write_text(
        lesson_text("stable-id", topic="not-derived-from-path"),
        encoding="utf-8",
    )

    report = check_markdown_files([path])

    assert report.valid
    assert report.checked_files == (path.resolve().as_posix(),)


def test_cli_json_for_file_outside_vault_is_only_stdout_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    external = tmp_path / "external.md"
    external.write_text(lesson_text("external"), encoding="utf-8")

    code = run_cli(
        ["doctor", "--vault", str(vault), "--json", str(external)]
    )

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert code == 2
    assert output.err == ""
    assert payload["valid"] is False
    assert payload["files_checked"] == 0
    assert payload["problems"] == []
    assert "fuori dalla radice del vault" in payload["operational_error"]


def test_symlink_in_vault_pointing_outside_is_an_operational_error(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    topic_dir = vault / "python"
    topic_dir.mkdir(parents=True)
    external = tmp_path / "external.md"
    external.write_text(lesson_text("python/external"), encoding="utf-8")
    link = topic_dir / "external.md"
    try:
        link.symlink_to(external)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink non disponibili: {exc}")

    with pytest.raises(DoctorOperationalError, match="fuori dalla radice del vault"):
        check_markdown_files([link], vault_dir=vault)


def test_recursive_vault_scan_rejects_symlink_pointing_outside(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    topic_dir = vault / "python"
    topic_dir.mkdir(parents=True)
    external = tmp_path / "external.md"
    external.write_text(lesson_text("python/external"), encoding="utf-8")
    link = topic_dir / "external.md"
    try:
        link.symlink_to(external)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink non disponibili: {exc}")

    with pytest.raises(DoctorOperationalError, match="fuori dalla radice del vault"):
        check_markdown_files([], vault_dir=vault)


def test_empty_vault_is_valid(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    report = check_markdown_files([], vault_dir=vault)

    assert report.valid
    assert report.files_checked == 0
    assert report.unique_ids == 0
    assert report.problems == ()


def test_doctor_does_not_write_or_change_mtime_and_mode(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    first = write_valid(vault, "python/first.md")
    second = write_valid(vault, "linux/second.md")
    os.chmod(first, 0o640)
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in (first, second)
    }

    report = check_markdown_files([], vault_dir=vault)

    after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        for path in (first, second)
    }
    assert report.valid
    assert after == before
