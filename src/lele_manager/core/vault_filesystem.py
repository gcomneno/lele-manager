"""Application filesystem ownership checks, without following linked entries.

These checks bound ordinary local operations; they are not an OS sandbox or a
transaction against concurrent changes by another process.
"""
from __future__ import annotations

import stat
from pathlib import Path


class VaultFilesystemError(OSError):
    """A path cannot be proved to belong to its selected Vault."""


def assert_owned_path(path: Path, *, directory: bool = False) -> Path:
    """Reject linked/special nodes and linked ancestors, allowing missing paths."""
    absolute = path.absolute()
    for current in (*reversed(absolute.parents), absolute):
        try:
            node = current.lstat()
        except FileNotFoundError:
            continue
        is_directory = current != absolute or directory
        if stat.S_ISLNK(node.st_mode):
            raise VaultFilesystemError(f"symlinked path is unsafe: {current}")
        if is_directory:
            if not stat.S_ISDIR(node.st_mode):
                raise VaultFilesystemError(f"directory path is unsafe: {current}")
        elif not stat.S_ISREG(node.st_mode) or node.st_nlink != 1:
            raise VaultFilesystemError(f"file path is special or hard-linked: {current}")
    return path


def owned_tree_files(root: Path) -> list[Path]:
    """Inventory regular files, refusing symlinks, hard links and special nodes.

    Complete preflight prevents a later unsafe entry from allowing partial
    import/frontmatter writes. Non-Markdown regular files remain unmanaged.
    """
    assert_owned_path(root, directory=True)
    files: list[Path] = []
    if not root.exists():
        return files

    def visit(directory: Path) -> None:
        for path in sorted(directory.iterdir()):
            node = path.lstat()
            if stat.S_ISDIR(node.st_mode):
                visit(path)
            elif stat.S_ISREG(node.st_mode) and node.st_nlink == 1:
                files.append(path)
            else:
                raise VaultFilesystemError(f"Vault contains a linked or special entry: {path}")

    visit(root)
    return files


def owned_markdown_paths(root: Path) -> list[Path]:
    return sorted(path for path in owned_tree_files(root) if path.suffix.lower() == ".md")


def owned_destination(root: Path, relative_path: str) -> Path:
    """Validate a canonical destination before mkdir or any write."""
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise VaultFilesystemError("refusing to write outside vault")
    assert_owned_path(root, directory=True)
    return assert_owned_path(root / relative)
