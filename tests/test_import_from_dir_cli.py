import json
import os
import subprocess
import sys
from pathlib import Path

import textwrap
import yaml

import pytest

from lele_manager.cli import import_from_dir as import_cli


def run_cmd(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Helper per eseguire un comando Python -m ... in modo robusto."""
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(project_root / "src"), env.get("PYTHONPATH", "")]
    )
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _parse_frontmatter(md_text: str) -> dict:
    lines = md_text.splitlines()
    assert lines and lines[0].strip() == "---"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    assert end is not None, "frontmatter non chiuso"
    fm = "\n".join(lines[1:end])
    data = yaml.safe_load(fm) or {}
    assert isinstance(data, dict)
    return data


def test_import_from_dir_basic(tmp_path: Path) -> None:
    """Import semplice da una mini-vault con 1 file .md con frontmatter completo.

    Verifica:
    - il JSONL viene scritto;
    - c'è una sola riga;
    - topic/source/importance vengono preservati;
    - la data YAML viene normalizzata a stringa (YYYY-MM-DD) nel record.
    """
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    md_path = vault_dir / "test-lesson.md"
    md_path.write_text(
        textwrap.dedent(
            """\
            ---
            id: test/2025-01-01.sample
            topic: test-topic
            source: note
            importance: 3
            tags: [foo, bar]
            date: 2025-01-01
            title: "Sample LeLe"
            ---

            Contenuto della lesson di test.
            """
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "lessons.jsonl"

    cmd = [
        sys.executable,
        "-m",
        "lele_manager.cli.import_from_dir",
        str(vault_dir),
        str(output_path),
        "--on-duplicate",
        "overwrite",
        "--default-source",
        "note",
        "--default-importance",
        "3",
        "--write-missing-frontmatter",
    ]
    result = run_cmd(cmd)

    assert (
        result.returncode == 0
    ), f"import_from_dir failed: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    assert output_path.exists(), "Il file JSONL non è stato creato"

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, f"Attese 1 LeLe, trovate {len(lines)}"

    record = json.loads(lines[0])

    assert record.get("topic") == "test-topic"
    assert record.get("source") == "note"
    assert record.get("importance") == 3

    # YAML può parse-are date come datetime.date: nel record vogliamo stringa.
    assert record.get("date") == "2025-01-01"

    assert "Contenuto della lesson di test." in record.get("text", "")


def test_import_from_dir_missing_frontmatter_writes_required_fields(tmp_path: Path) -> None:
    """Se manca il frontmatter e usiamo --write-missing-frontmatter,
    deve essere creato con almeno: id/topic/source/importance (+ date se deducibile).
    """
    vault_dir = tmp_path / "vault"
    (vault_dir / "python").mkdir(parents=True)

    md_path = vault_dir / "python" / "2025-11-20.cin-vs-getline.md"
    md_path.write_text(
        "Contenuto senza frontmatter.\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "lessons.jsonl"

    cmd = [
        sys.executable,
        "-m",
        "lele_manager.cli.import_from_dir",
        str(vault_dir),
        str(output_path),
        "--on-duplicate",
        "overwrite",
        "--default-source",
        "note",
        "--default-importance",
        "3",
        "--write-missing-frontmatter",
    ]
    result = run_cmd(cmd)

    assert (
        result.returncode == 0
    ), f"import_from_dir failed: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])

    assert record["id"] == "python/2025-11-20.cin-vs-getline"
    assert record["topic"] == "python"
    assert record["source"] == "note"
    assert record["importance"] == 3
    assert record["date"] == "2025-11-20"

    # Verifica che il file sia stato riscritto con frontmatter completo
    md_text = md_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(md_text)
    assert fm.get("id") == "python/2025-11-20.cin-vs-getline"
    assert fm.get("topic") == "python"
    assert fm.get("source") == "note"
    assert fm.get("importance") == 3
    assert fm.get("date") == "2025-11-20"


def test_import_from_dir_on_duplicate_error(tmp_path: Path) -> None:
    """Due file con lo stesso id + --on-duplicate error -> comando deve fallire."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    frontmatter = textwrap.dedent(
        """\
        ---
        id: duplicate/2025-01-01.sample
        topic: test-topic
        source: note
        importance: 3
        date: 2025-01-01
        title: "Duplicate LeLe"
        ---
        Corpo.
        """
    )

    (vault_dir / "a.md").write_text(frontmatter, encoding="utf-8")
    (vault_dir / "b.md").write_text(frontmatter, encoding="utf-8")

    output_path = tmp_path / "lessons.jsonl"

    cmd = [
        sys.executable,
        "-m",
        "lele_manager.cli.import_from_dir",
        str(vault_dir),
        str(output_path),
        "--on-duplicate",
        "error",
        "--default-source",
        "note",
        "--default-importance",
        "3",
        "--write-missing-frontmatter",
    ]
    result = run_cmd(cmd)

    assert result.returncode != 0, "on-duplicate=error con id duplicati doveva fallire"


def test_import_from_dir_on_duplicate_skip_keeps_first(tmp_path: Path) -> None:
    """Due file con stesso id + on-duplicate=skip: deve vincere il primo file."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    (vault_dir / "a.md").write_text(
        textwrap.dedent(
            """\
            ---
            id: dup/1
            topic: t
            source: note
            importance: 3
            ---
            PRIMO
            """
        ),
        encoding="utf-8",
    )
    (vault_dir / "b.md").write_text(
        textwrap.dedent(
            """\
            ---
            id: dup/1
            topic: t
            source: note
            importance: 3
            ---
            SECONDO
            """
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "lessons.jsonl"

    cmd = [
        sys.executable,
        "-m",
        "lele_manager.cli.import_from_dir",
        str(vault_dir),
        str(output_path),
        "--on-duplicate",
        "skip",
        "--default-source",
        "note",
        "--default-importance",
        "3",
    ]
    result = run_cmd(cmd)

    assert (
        result.returncode == 0
    ), f"import_from_dir failed: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert "PRIMO" in record.get("text", "")
    assert "SECONDO" not in record.get("text", "")



def test_valid_frontmatter_is_byte_for_byte_unchanged(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    md_path = vault_dir / "valid.md"
    original = textwrap.dedent(
        """\
        ---
        id: test/valid
        topic: scrittura
        source: note
        importance: 3
        tags: [italiano, qualità]
        date: 2025-12-05
        title: "Perché — è importante"
        ---

        Testo già valido con accenti.
        """
    ).encode("utf-8")
    md_path.write_bytes(original)

    output_path = tmp_path / "lessons.jsonl"
    result = run_cmd(
        [
            sys.executable,
            "-m",
            "lele_manager.cli.import_from_dir",
            str(vault_dir),
            str(output_path),
            "--default-source",
            "note",
            "--default-importance",
            "3",
            "--write-missing-frontmatter",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert md_path.read_bytes() == original


def test_required_rewrite_preserves_unicode_and_field_order(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    md_path = vault_dir / "unicode.md"
    md_path.write_text(
        textwrap.dedent(
            """\
            ---
            id: test/unicode
            topic: qualità
            source: note
            title: "Perché — già così"
            tags: [caffè, città]
            ---

            È un contenuto leggibile.
            """
        ),
        encoding="utf-8",
    )

    result = run_cmd(
        [
            sys.executable,
            "-m",
            "lele_manager.cli.import_from_dir",
            str(vault_dir),
            str(tmp_path / "lessons.jsonl"),
            "--default-importance",
            "3",
            "--write-missing-frontmatter",
        ]
    )

    assert result.returncode == 0, result.stderr
    rewritten = md_path.read_text(encoding="utf-8")
    assert "qualità" in rewritten
    assert "Perché — già così" in rewritten
    assert "caffè" in rewritten
    assert "\\u" not in rewritten
    assert "\\x" not in rewritten
    assert rewritten.index("title:") < rewritten.index("tags:") < rewritten.index("importance:")
    assert _parse_frontmatter(rewritten)["importance"] == 3


def test_jsonl_normalizes_metadata_without_rewriting_source(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    md_path = vault_dir / "normalized.md"
    original = textwrap.dedent(
        """\
        ---
        id: test/normalized
        topic: test
        source: note
        importance: "4"
        tags: "python, pytest"
        date: 2025-12-05
        ---
        Body.
        """
    ).encode("utf-8")
    md_path.write_bytes(original)
    output_path = tmp_path / "lessons.jsonl"

    result = run_cmd(
        [
            sys.executable,
            "-m",
            "lele_manager.cli.import_from_dir",
            str(vault_dir),
            str(output_path),
            "--write-missing-frontmatter",
        ]
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert record["date"] == "2025-12-05"
    assert record["importance"] == 4
    assert record["tags"] == ["python", "pytest"]
    assert record["frontmatter"]["date"] == "2025-12-05"
    assert md_path.read_bytes() == original


def test_valid_vault_import_does_not_modify_sources(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    sources = {
        "a.md": b"---\nid: vault/a\ntopic: alpha\nsource: note\nimportance: 3\ntags: [alpha]\ndate: 2025-01-01\ntitle: LeLe A\n---\nA\n",
        "b.md": "---\nid: vault/b\ntopic: beta\nsource: note\nimportance: 5\ntags: [città]\ndate: 2025-01-02\ntitle: LeLe B\n---\nB — è valido\n".encode("utf-8"),
    }
    for name, content in sources.items():
        (vault_dir / name).write_bytes(content)
    output_path = tmp_path / "lessons.jsonl"

    result = run_cmd(
        [
            sys.executable,
            "-m",
            "lele_manager.cli.import_from_dir",
            str(vault_dir),
            str(output_path),
            "--default-source",
            "note",
            "--default-importance",
            "3",
            "--write-missing-frontmatter",
        ]
    )

    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert [(record["id"], record["date"]) for record in records] == [
        ("vault/a", "2025-01-01"),
        ("vault/b", "2025-01-02"),
    ]
    assert {name: (vault_dir / name).read_bytes() for name in sources} == sources


def _dry_run(vault: Path, output: Path, *extra: str) -> subprocess.CompletedProcess:
    return run_cmd(
        [
            sys.executable,
            "-m",
            "lele_manager.cli.import_from_dir",
            str(vault),
            str(output),
            "--dry-run",
            *extra,
        ]
    )


def _lesson(path: Path, lesson_id: str, body: str = "Body") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {lesson_id}\ntopic: topic\nsource: manual\nimportance: 3\n---\n{body}\n",
        encoding="utf-8",
    )


def test_parse_args_accepts_dry_run() -> None:
    assert import_cli.parse_args(["vault", "out.jsonl", "--dry-run"]).dry_run is True


def test_dry_run_does_not_create_output_or_parent_and_is_deterministic(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    _lesson(vault / "lesson.MD", "uppercase")
    output = tmp_path / "missing" / "nested" / "lessons.jsonl"

    first = _dry_run(vault, output)
    second = _dry_run(vault, output)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert "create=1" in first.stdout
    assert "uppercase — lesson.MD" in first.stdout
    assert not output.exists()
    assert not output.parent.exists()


def test_dry_run_preserves_existing_output_and_source_with_pending_write(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    markdown = vault / "topic" / "2025-01-01.lesson.md"
    markdown.parent.mkdir(parents=True)
    markdown.write_bytes(b"Body without frontmatter\n")
    original_source = markdown.read_bytes()
    output = tmp_path / "lessons.jsonl"
    output.write_bytes(b'{"id":"old","text":"untouched"}\n')
    original_output = output.read_bytes()

    result = _dry_run(vault, output, "--write-missing-frontmatter")

    assert result.returncode == 0
    assert "pending source writes:" in result.stdout
    assert "topic/2025-01-01.lesson.md" in result.stdout
    assert output.read_bytes() == original_output
    assert markdown.read_bytes() == original_source


def test_dry_run_never_calls_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    _lesson(vault / "one.md", "one")

    class Snapshot:
        def list(self) -> tuple[dict[str, object], ...]:
            return ()

    class SpyStore:
        def snapshot(self) -> Snapshot:
            return Snapshot()

        def publish(self, records: object) -> None:
            pytest.fail(f"publish called with {records!r}")

    monkeypatch.setattr(import_cli, "projection_store", lambda path: SpyStore())
    import_cli.main([str(vault), str(tmp_path / "out.jsonl"), "--dry-run"])


def test_dry_run_reports_all_change_kinds(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _lesson(vault / "same.md", "same")
    _lesson(vault / "changed.md", "changed", "new")
    _lesson(vault / "new.md", "new")
    baseline = import_cli.analyze_import_from_dir(
        vault, "overwrite", "manual", 3, None, False
    )
    same = dict(baseline.candidate_records["same"])
    changed = dict(baseline.candidate_records["changed"])
    changed["text"] = "old"
    output = tmp_path / "lessons.jsonl"
    output.write_text(
        "\n".join(json.dumps(record) for record in [same, changed, {"id": "removed"}])
        + "\n",
        encoding="utf-8",
    )

    result = _dry_run(vault, output)

    assert result.returncode == 0
    assert "Riepilogo: create=1, update=1, unchanged=1, removed=1" in result.stdout
    for expected in ("new — new.md", "changed — changed.md", "same — same.md", "removed"):
        assert expected in result.stdout


@pytest.mark.parametrize(
    ("policy", "returncode", "resolution"),
    [("error", 1, "blocked"), ("skip", 0, "kept_first"), ("overwrite", 0, "kept_last")],
)
def test_dry_run_duplicate_exit_codes(
    tmp_path: Path, policy: str, returncode: int, resolution: str
) -> None:
    vault = tmp_path / policy
    _lesson(vault / "a.md", "dup", "first")
    _lesson(vault / "b.md", "dup", "second")

    result = _dry_run(vault, tmp_path / f"{policy}.jsonl", "--on-duplicate", policy)

    assert result.returncode == returncode
    assert f"policy={policy}; risoluzione={resolution}" in result.stdout
    assert "Nessuna modifica applicata." in result.stdout


def test_dry_run_reports_ignored_and_malformed_yaml(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "ignored.txt").write_text("ignored", encoding="utf-8")
    (vault / "bad.md").write_text("---\nid: [broken\n---\nBody\n", encoding="utf-8")

    result = _dry_run(vault, tmp_path / "out.jsonl")

    assert result.returncode == 0
    assert "[non bloccante] malformed_yaml — bad.md" in result.stdout
    assert "ignored.txt: not_markdown" in result.stdout


def test_dry_run_empty_directory_does_not_report_total_removal(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    output = tmp_path / "lessons.jsonl"
    output.write_text('{"id":"existing"}\n', encoding="utf-8")

    result = _dry_run(vault, output)

    assert result.returncode == 0
    assert "removed=0" in result.stdout
    assert "Pubblicazione replace-all: non avverrebbe." in result.stdout



def test_dry_run_missing_input_is_global_error_without_side_effects(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "missing-vault"
    output = tmp_path / "missing-output" / "lessons.jsonl"

    result = _dry_run(vault, output)

    assert result.returncode == 2
    assert "Directory di input non trovata" in result.stderr
    assert result.stdout == ""
    assert not output.exists()
    assert not output.parent.exists()

@pytest.mark.parametrize(
    "existing_output",
    [
        b"not-json\n",
        b'{"id":"duplicate"}\n{"id":"duplicate"}\n',
    ],
)
def test_dry_run_rejects_invalid_existing_snapshot_without_modifying_it(
    tmp_path: Path, existing_output: bytes
) -> None:
    vault = tmp_path / "vault"
    _lesson(vault / "lesson.md", "lesson")
    output = tmp_path / "lessons.jsonl"
    output.write_bytes(existing_output)

    result = _dry_run(vault, output)

    assert result.returncode == 2
    assert "Output corrente non valido o non leggibile" in result.stderr
    assert result.stdout == ""
    assert output.read_bytes() == existing_output
