from pathlib import Path

import yaml

from lele_manager.cli.import_from_dir import import_from_dir


def _read_frontmatter(md_text: str) -> dict:
    lines = md_text.splitlines()
    assert lines and lines[0].strip() == "---"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    assert end is not None
    fm = "\n".join(lines[1:end])
    data = yaml.safe_load(fm) or {}
    assert isinstance(data, dict)
    return data


def test_import_writes_missing_frontmatter_fields(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "python").mkdir(parents=True)

    md = vault / "python" / "2025-11-20.cin-vs-getline.md"
    md.write_text("Contenuto senza frontmatter.\n", encoding="utf-8")

    records = import_from_dir(
        input_dir=vault,
        on_duplicate="overwrite",
        default_source="note",
        default_importance=3,
        default_topic=None,
        write_missing_frontmatter=True,
    )

    assert len(records) == 1
    rec = records["python/2025-11-20.cin-vs-getline"]
    assert rec.topic == "python"
    assert rec.source == "note"
    assert rec.importance == 3
    assert rec.date == "2025-11-20"

    updated = md.read_text(encoding="utf-8")
    fm = _read_frontmatter(updated)
    assert fm["id"] == "python/2025-11-20.cin-vs-getline"
    assert fm["topic"] == "python"
    assert fm["source"] == "note"
    assert fm["importance"] == 3
    assert fm["date"] == "2025-11-20"


def test_import_normalizes_yaml_date_type_without_rewriting_source(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    md = vault / "x.md"
    md.write_text(
        """---
id: x/1
topic: t
source: note
importance: 3
date: 2025-01-01
---
Body
""",
        encoding="utf-8",
    )
    original = md.read_bytes()

    records = import_from_dir(
        input_dir=vault,
        on_duplicate="overwrite",
        default_source="note",
        default_importance=3,
        default_topic=None,
        write_missing_frontmatter=True,
    )

    rec = records["x/1"]
    assert rec.date == "2025-01-01"
    assert rec.frontmatter["date"] == "2025-01-01"
    assert md.read_bytes() == original


def test_overwrite_updates_only_winning_duplicate_source(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    paths = [vault / name for name in ("a.md", "b.md", "c.md")]
    for index, path in enumerate(paths, start=1):
        path.write_text(f"---\nid: dup\n---\nbody {index}\n", encoding="utf-8")
    originals = [path.read_bytes() for path in paths]

    records = import_from_dir(vault, "overwrite", "note", 3, None, True)

    assert records["dup"].text == "body 3"
    assert [path.read_bytes() for path in paths[:2]] == originals[:2]
    assert paths[2].read_bytes() != originals[2]
