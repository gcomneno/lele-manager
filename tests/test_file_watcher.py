from pathlib import Path

from lele_manager.cli.file_watcher import snapshot

def test_snapshot_returns_only_files(tmp_path: Path) -> None:
    root = tmp_path / "watched"
    root.mkdir()

    file1 = root / "a.txt"
    file1.write_text("hello")

    subdir = root / "sub"
    subdir.mkdir()
    file2 = subdir / "b.txt"
    file2.write_text("world")

    snap = snapshot(root)

    # Deve contenere entrambi i file, nessuna directory
    assert file1 in snap
    assert file2 in snap
    assert all(p.is_file() for p in snap.keys())
