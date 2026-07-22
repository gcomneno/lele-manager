"""Collision-safe filesystem adapter for canonical candidate approval."""

from __future__ import annotations

from collections.abc import Mapping
import math
import os
from pathlib import Path
import tempfile

from lele_manager.application.candidate_approval import (
    CanonicalIdentityCollisionError,
    CanonicalLessonSpec,
    CanonicalPathCollisionError,
    CanonicalVaultStorageError,
    VaultWriteOutcome,
)
from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.core.vault import render_lesson_markdown


def _plain(value: object, active: set[int] | None = None) -> object:
    active = set() if active is None else active
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise CanonicalVaultStorageError(
                "canonical provenance mapping keys must be strings"
            )
        identity = id(value)
        if identity in active:
            raise CanonicalVaultStorageError("canonical provenance must not be cyclic")
        active.add(identity)
        try:
            return {key: _plain(value[key], active) for key in sorted(value)}
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise CanonicalVaultStorageError("canonical provenance must not be cyclic")
        active.add(identity)
        try:
            return [_plain(item, active) for item in value]
        finally:
            active.remove(identity)
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise CanonicalVaultStorageError(
        "canonical provenance must contain only JSON-compatible values"
    )


class FilesystemCanonicalMarkdownVault:
    """Publish fully rendered UTF-8 bytes without replacing existing files."""

    def __init__(self, vault_dir: Path) -> None:
        self._vault_dir = vault_dir

    def publish(self, lesson: CanonicalLessonSpec) -> VaultWriteOutcome:
        temporary: Path | None = None
        try:
            root = self._vault_dir.resolve()
            destination = (root / lesson.relative_path).resolve()
            try:
                destination.relative_to(root)
            except ValueError:
                raise CanonicalVaultStorageError(
                    "invalid relative vault path"
                ) from None
            if destination.suffix.lower() != ".md":
                raise CanonicalVaultStorageError("invalid relative vault path")

            rendered = render_lesson_markdown(
                lesson_id=lesson.lesson_id,
                body=lesson.body,
                topic=lesson.topic,
                source=lesson.source,
                importance=lesson.importance,
                tags=list(lesson.tags),
                date=lesson.date,
                title=lesson.title,
                provenance=_plain(lesson.provenance),  # type: ignore[arg-type]
            ).encode("utf-8")

            root.mkdir(parents=True, exist_ok=True)
            for path in sorted(root.rglob("*.md")):
                content = path.read_bytes()
                frontmatter, _ = parse_markdown_with_frontmatter(
                    content.decode("utf-8")
                )
                if (
                    frontmatter.get("id") == lesson.lesson_id
                    and path.resolve() != destination
                ):
                    raise CanonicalIdentityCollisionError("lesson ID exists elsewhere")

            if destination.exists():
                if not destination.is_file() or destination.read_bytes() != rendered:
                    raise CanonicalPathCollisionError("destination is occupied")
                return VaultWriteOutcome.IDENTICAL

            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as target:
                temporary = Path(target.name)
                target.write(rendered)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.is_file() and destination.read_bytes() == rendered:
                    return VaultWriteOutcome.IDENTICAL
                raise CanonicalPathCollisionError("destination is occupied") from None
            return VaultWriteOutcome.CREATED
        except (
            CanonicalPathCollisionError,
            CanonicalIdentityCollisionError,
            CanonicalVaultStorageError,
        ):
            raise
        except (OSError, UnicodeError):
            raise CanonicalVaultStorageError("vault I/O failed") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def verify(self, lesson: CanonicalLessonSpec) -> VaultWriteOutcome:
        """Verify an approved candidate's exact artifact without creating it."""
        try:
            root = self._vault_dir.resolve()
            destination = (root / lesson.relative_path).resolve()
            destination.relative_to(root)
            rendered = render_lesson_markdown(
                lesson_id=lesson.lesson_id,
                body=lesson.body,
                topic=lesson.topic,
                source=lesson.source,
                importance=lesson.importance,
                tags=list(lesson.tags),
                date=lesson.date,
                title=lesson.title,
                provenance=_plain(lesson.provenance),  # type: ignore[arg-type]
            ).encode("utf-8")
            for path in sorted(root.rglob("*.md")):
                content = path.read_bytes()
                frontmatter, _ = parse_markdown_with_frontmatter(
                    content.decode("utf-8")
                )
                if (
                    frontmatter.get("id") == lesson.lesson_id
                    and path.resolve() != destination
                ):
                    raise CanonicalIdentityCollisionError("lesson ID exists elsewhere")
            if not destination.is_file() or destination.read_bytes() != rendered:
                raise CanonicalPathCollisionError(
                    "canonical lesson is missing or changed"
                )
            return VaultWriteOutcome.IDENTICAL
        except (
            CanonicalPathCollisionError,
            CanonicalIdentityCollisionError,
            CanonicalVaultStorageError,
        ):
            raise
        except (OSError, UnicodeError, ValueError):
            raise CanonicalVaultStorageError("vault verification failed") from None
