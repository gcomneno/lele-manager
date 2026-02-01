import json
import subprocess
import sys
from pathlib import Path

import textwrap
import yaml


def run_cmd(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Helper per eseguire un comando Python -m ... in modo robusto."""
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
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
