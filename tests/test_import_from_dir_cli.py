import json
import subprocess
import sys
from pathlib import Path

import textwrap


def run_cmd(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Helper per eseguire un comando Python -m ... in modo robusto."""
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )


def test_import_from_dir_basic(tmp_path: Path) -> None:
    """Import semplice da una mini-vault con 1 file .md con frontmatter completo.

    Verifica:
    - il JSONL viene scritto;
    - c'è una sola riga;
    - il campo 'topic' viene preservato;
    - il record contiene i campi chiave (topic/source/importance),
      e il campo 'date' non causa problemi di serializzazione.
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

    # Se il comando fallisce, voglio vedere subito stderr nel test
    assert (
        result.returncode == 0
    ), f"import_from_dir failed: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    assert output_path.exists(), "Il file JSONL non è stato creato"

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, f"Attese 1 LeLe, trovate {len(lines)}"

    record = json.loads(lines[0])

    # Non assumo troppo su 'id', ma mi aspetto almeno topic/source/importance giusti
    assert record.get("topic") == "test-topic"
    assert record.get("source") == "note"
    assert record.get("importance") == 3

    # La data: l'import attuale può anche NON salvarla esplicitamente.
    # Verifichiamo solo che:
    # - il campo esista se lo schema lo prevede,
    # - e che non sia un tipo "strano" non JSON-serializzabile.
    date_value = record.get("date", None)
    assert date_value is None or isinstance(
        date_value, str
    ), f"date deve essere None o string, non {type(date_value)!r}"

    # Il testo deve contenere il body
    assert "Contenuto della lesson di test." in record.get("text", "")


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

    # Qui vogliamo esplicitamente che fallisca
    assert result.returncode != 0, "on-duplicate=error con id duplicati doveva fallire"
    # (In futuro possiamo raffinare l'assert sul messaggio di errore.)
