"""Canonical lesson write primitives and maintained revision boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import os
from pathlib import Path
import stat
import tempfile
from typing import Callable

from lele_manager.cli.import_from_dir import (
    derive_date,
    normalize_tags,
    parse_markdown_with_frontmatter,
)
from lele_manager.core.canonical_mutation import canonical_mutation_boundary
from lele_manager.core.lesson_revision_history import (
    LessonRevision,
    LessonRevisionHistoryError,
    LessonRevisionHistoryStore,
    canonical_fingerprint,
)
from lele_manager.core.lifecycle import (
    LifecycleState,
    LifecycleValidationError,
    normalize_lifecycle,
    normalize_superseded_by,
)
from lele_manager.core.relationships import (
    CanonicalRelationships,
    RelationshipValidationError,
    normalize_relationships,
)
from lele_manager.core.vault import (
    find_markdown_paths_by_id,
    render_lesson_markdown,
    write_lesson_markdown,
)


class CanonicalLessonWriteError(Exception):
    pass


class CanonicalLessonWriteNotFoundError(CanonicalLessonWriteError):
    pass


class CanonicalLessonWriteAmbiguousError(CanonicalLessonWriteError):
    pass


class CanonicalLessonWriteStorageError(CanonicalLessonWriteError):
    pass


class CanonicalLessonWriteStaleError(CanonicalLessonWriteError):
    pass


class CanonicalLessonWriteHistoryError(CanonicalLessonWriteError):
    pass


class CanonicalLessonWriteRecoveryError(CanonicalLessonWriteError):
    pass


class CanonicalLessonRollbackTargetError(CanonicalLessonWriteError):
    pass


@dataclass(frozen=True)
class CanonicalLessonRevisionState:
    relative_path: str
    canonical_revision: str


@dataclass(frozen=True)
class CanonicalLessonSnapshot:
    lesson_id: str
    relative_path: str
    canonical_revision: str
    text: str
    topic: str | None
    source: str | None
    importance: int | None
    tags: list[str]
    date: str | None
    title: str | None
    lifecycle: LifecycleState
    superseded_by: str | None
    relationships: CanonicalRelationships


@dataclass(frozen=True)
class CanonicalLessonRevisionWriteResult:
    path: Path
    canonical_revision: str
    revision: int | None
    canonical_changed: bool


def _resolve_exact_canonical(
    vault_dir: Path,
    lesson_id: str,
) -> tuple[Path, str]:
    matches = find_markdown_paths_by_id(vault_dir, lesson_id)
    if not matches:
        raise CanonicalLessonWriteNotFoundError("canonical lesson was not found")
    if len(matches) != 1:
        raise CanonicalLessonWriteAmbiguousError(
            "canonical lesson identity is ambiguous"
        )
    path = matches[0]
    try:
        relative_path = (
            path.resolve()
            .relative_to(vault_dir.resolve())
            .as_posix()
        )
    except (OSError, ValueError) as exc:
        raise CanonicalLessonWriteStorageError(
            "canonical lesson path could not be resolved"
        ) from exc
    return path, relative_path


def _optional_frontmatter_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def read_canonical_lesson_snapshot(
    *,
    vault_dir: Path,
    lesson_id: str,
) -> CanonicalLessonSnapshot:
    """Read one coherent canonical authoring snapshot.

    Editable fields and the optimistic-concurrency fingerprint are derived from
    the same exact Markdown bytes. Derived projection state must not be mixed
    into this authoring snapshot.
    """
    path, relative_path = _resolve_exact_canonical(vault_dir, lesson_id)
    try:
        raw = path.read_bytes()
        markdown = raw.decode("utf-8")
        frontmatter, body = parse_markdown_with_frontmatter(markdown)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        raise CanonicalLessonWriteStorageError(
            "canonical lesson could not be read"
        ) from exc

    raw_importance = frontmatter.get("importance")
    importance: int | None
    if isinstance(raw_importance, (int, float, str)):
        try:
            importance = int(raw_importance)
        except ValueError:
            importance = None
    else:
        importance = None

    try:
        lifecycle = normalize_lifecycle(frontmatter.get("lifecycle"))
        superseded_by = normalize_superseded_by(
            frontmatter.get("superseded_by"),
            lesson_id=lesson_id,
        )
        relationships = normalize_relationships(
            frontmatter.get("relationships"),
            lesson_id=lesson_id,
        )
    except (LifecycleValidationError, RelationshipValidationError) as exc:
        raise CanonicalLessonWriteStorageError(
            "canonical lesson metadata is invalid"
        ) from exc

    return CanonicalLessonSnapshot(
        lesson_id=lesson_id,
        relative_path=relative_path,
        canonical_revision=canonical_fingerprint(raw),
        text=body.strip(),
        topic=_optional_frontmatter_string(frontmatter.get("topic")),
        source=_optional_frontmatter_string(frontmatter.get("source")),
        importance=importance,
        tags=normalize_tags(frontmatter.get("tags")),
        date=derive_date(frontmatter, path),
        title=_optional_frontmatter_string(frontmatter.get("title")),
        lifecycle=lifecycle,
        superseded_by=superseded_by,
        relationships=relationships,
    )


def read_canonical_lesson_revision(
    *,
    vault_dir: Path,
    lesson_id: str,
) -> CanonicalLessonRevisionState:
    """Return the exact-byte concurrency token for one canonical LeLe."""
    path, relative_path = _resolve_exact_canonical(vault_dir, lesson_id)
    try:
        current = path.read_bytes()
    except OSError as exc:
        raise CanonicalLessonWriteStorageError(
            "canonical lesson could not be read"
        ) from exc
    return CanonicalLessonRevisionState(
        relative_path=relative_path,
        canonical_revision=canonical_fingerprint(current),
    )


def write_canonical_lesson_source(
    *, vault_dir: Path, lesson_id: str, body: str, topic: str, source: str,
    importance: int, tags: list[str], date: str, title: str | None,
    lifecycle: LifecycleState, superseded_by: str | None,
    invalidate_cache: Callable[[], None],
    relationships: CanonicalRelationships | None = None,
) -> Path:
    """Rewrite exactly one existing canonical Markdown source without refresh."""
    path, relative_path = _resolve_exact_canonical(vault_dir, lesson_id)
    relationship_state = (
        read_canonical_lesson_snapshot(
            vault_dir=vault_dir,
            lesson_id=lesson_id,
        ).relationships
        if relationships is None
        else relationships
    )
    try:
        result = write_lesson_markdown(
            vault_dir, lesson_id=lesson_id, body=body, topic=topic, source=source,
            importance=importance, tags=tags, date=date, title=title,
            relative_path=relative_path, lifecycle=lifecycle,
            superseded_by=superseded_by,
            relationships=relationship_state,
        )
    except (OSError, ValueError) as exc:
        raise CanonicalLessonWriteStorageError(
            "canonical lesson could not be written"
        ) from exc
    invalidate_cache()
    return result


def write_revisioned_canonical_lesson_source(
    *,
    vault_dir: Path,
    lesson_id: str,
    expected_revision: str,
    history_store: LessonRevisionHistoryStore,
    body: str,
    topic: str,
    source: str,
    importance: int,
    tags: list[str],
    date: str,
    title: str | None,
    lifecycle: LifecycleState,
    superseded_by: str | None,
    invalidate_cache: Callable[[], None],
    relationships: CanonicalRelationships | None = None,
    occurred_at: str | None = None,
    reason: str | None = None,
) -> CanonicalLessonRevisionWriteResult:
    """Revision-aware canonical edit without derived refresh.

    Exact current bytes are checked inside the shared mutation boundary.
    The first maintained edit records revision 0 as baseline. Successful
    canonical changes append exactly one edit revision. Identical writes are
    no-ops and do not manufacture history.
    """
    with canonical_mutation_boundary():
        path, relative_path = _resolve_exact_canonical(vault_dir, lesson_id)

        try:
            current_bytes = path.read_bytes()
            current_markdown = current_bytes.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise CanonicalLessonWriteStorageError(
                "canonical lesson could not be read"
            ) from exc

        try:
            current_frontmatter, _ = parse_markdown_with_frontmatter(
                current_markdown
            )
            current_relationships = normalize_relationships(
                current_frontmatter.get("relationships"),
                lesson_id=lesson_id,
            )
        except RelationshipValidationError as exc:
            raise CanonicalLessonWriteStorageError(
                "canonical lesson relationship metadata is invalid"
            ) from exc

        relationship_state = (
            current_relationships
            if relationships is None
            else relationships
        )

        current_revision = canonical_fingerprint(current_bytes)
        if current_revision != expected_revision:
            raise CanonicalLessonWriteStaleError(
                "canonical lesson changed since it was loaded"
            )

        try:
            revisions = history_store.list(lesson_id)
        except LessonRevisionHistoryError as exc:
            raise CanonicalLessonWriteHistoryError(
                "lesson revision history is unavailable"
            ) from exc

        if revisions and revisions[-1].canonical_fingerprint != current_revision:
            raise CanonicalLessonWriteHistoryError(
                "canonical lesson and maintained revision history diverged"
            )

        rendered = render_lesson_markdown(
            lesson_id=lesson_id,
            body=body,
            topic=topic,
            source=source,
            importance=importance,
            tags=tags,
            date=date,
            title=title,
            lifecycle=lifecycle,
            superseded_by=superseded_by,
            relationships=relationship_state,
        )
        resulting_bytes = rendered.encode("utf-8")
        resulting_revision = canonical_fingerprint(resulting_bytes)

        if resulting_bytes == current_bytes:
            return CanonicalLessonRevisionWriteResult(
                path=path,
                canonical_revision=current_revision,
                revision=revisions[-1].revision if revisions else None,
                canonical_changed=False,
            )

        timestamp = occurred_at or datetime.now(timezone.utc).isoformat()

        if not revisions:
            baseline = LessonRevision(
                lesson_id=lesson_id,
                revision=0,
                canonical_fingerprint=current_revision,
                occurred_at=timestamp,
                action="baseline",
                relative_path=relative_path,
                markdown=current_markdown,
            )
            try:
                history_store.append(baseline)
            except LessonRevisionHistoryError as exc:
                raise CanonicalLessonWriteHistoryError(
                    "lesson baseline revision could not be saved"
                ) from exc
            next_revision = 1
        else:
            next_revision = revisions[-1].revision + 1

        try:
            result_path = write_lesson_markdown(
                vault_dir,
                lesson_id=lesson_id,
                body=body,
                topic=topic,
                source=source,
                importance=importance,
                tags=tags,
                date=date,
                title=title,
                relative_path=relative_path,
                lifecycle=lifecycle,
                superseded_by=superseded_by,
                relationships=relationship_state,
            )
        except (OSError, ValueError) as exc:
            raise CanonicalLessonWriteStorageError(
                "canonical lesson could not be written"
            ) from exc

        edit = LessonRevision(
            lesson_id=lesson_id,
            revision=next_revision,
            canonical_fingerprint=resulting_revision,
            occurred_at=timestamp,
            action="edit",
            relative_path=relative_path,
            markdown=rendered,
            reason=reason,
        )

        try:
            history_store.append(edit)
        except LessonRevisionHistoryError as history_exc:
            try:
                path.write_bytes(current_bytes)
            except OSError as recovery_exc:
                raise CanonicalLessonWriteRecoveryError(
                    "canonical write succeeded but history persistence and "
                    "canonical recovery both failed"
                ) from recovery_exc
            raise CanonicalLessonWriteHistoryError(
                "lesson revision could not be saved; canonical edit was recovered"
            ) from history_exc

        invalidate_cache()
        return CanonicalLessonRevisionWriteResult(
            path=result_path,
            canonical_revision=resulting_revision,
            revision=next_revision,
            canonical_changed=True,
        )


def diff_lesson_revisions(
    *,
    history_store: LessonRevisionHistoryStore,
    lesson_id: str,
    from_revision: int,
    to_revision: int,
) -> str:
    """Return a human-readable unified diff between immutable snapshots."""
    try:
        before = history_store.get(lesson_id, from_revision)
        after = history_store.get(lesson_id, to_revision)
    except LessonRevisionHistoryError as exc:
        raise CanonicalLessonRollbackTargetError(
            "lesson revision was not found"
        ) from exc

    return "".join(
        difflib.unified_diff(
            before.markdown.splitlines(keepends=True),
            after.markdown.splitlines(keepends=True),
            fromfile=f"revision-{from_revision}.md",
            tofile=f"revision-{to_revision}.md",
        )
    )


def _atomic_replace_exact(path: Path, data: bytes) -> None:
    """Replace one already-resolved regular canonical file atomically."""
    try:
        node = path.lstat()
    except OSError as exc:
        raise CanonicalLessonWriteStorageError(
            "canonical lesson could not be safely inspected"
        ) from exc

    if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
        raise CanonicalLessonWriteStorageError(
            "canonical lesson path is unsafe"
        )

    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IMODE(node.st_mode))

        current = path.lstat()
        if stat.S_ISLNK(current.st_mode) or not stat.S_ISREG(current.st_mode):
            raise CanonicalLessonWriteStorageError(
                "canonical lesson path changed while writing"
            )

        os.replace(temporary, path)
        temporary = None
    except CanonicalLessonWriteStorageError:
        raise
    except OSError as exc:
        raise CanonicalLessonWriteStorageError(
            "canonical lesson could not be written"
        ) from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def rollback_canonical_lesson_source(
    *,
    vault_dir: Path,
    lesson_id: str,
    target_revision: int,
    expected_revision: str,
    history_store: LessonRevisionHistoryStore,
    invalidate_cache: Callable[[], None],
    occurred_at: str | None = None,
    reason: str | None = None,
) -> CanonicalLessonRevisionWriteResult:
    """Restore one historical snapshot and append a new rollback revision."""
    with canonical_mutation_boundary():
        path, relative_path = _resolve_exact_canonical(vault_dir, lesson_id)

        try:
            current_bytes = path.read_bytes()
        except OSError as exc:
            raise CanonicalLessonWriteStorageError(
                "canonical lesson could not be read"
            ) from exc

        current_fingerprint = canonical_fingerprint(current_bytes)
        if current_fingerprint != expected_revision:
            raise CanonicalLessonWriteStaleError(
                "canonical lesson changed since it was loaded"
            )

        try:
            revisions = history_store.list(lesson_id)
        except LessonRevisionHistoryError as exc:
            raise CanonicalLessonWriteHistoryError(
                "lesson revision history is unavailable"
            ) from exc

        if not revisions:
            raise CanonicalLessonRollbackTargetError(
                "lesson has no maintained revision history"
            )

        if revisions[-1].canonical_fingerprint != current_fingerprint:
            raise CanonicalLessonWriteHistoryError(
                "canonical lesson and maintained revision history diverged"
            )

        if target_revision < 0 or target_revision >= len(revisions):
            raise CanonicalLessonRollbackTargetError(
                "lesson revision was not found"
            )

        if target_revision == revisions[-1].revision:
            raise CanonicalLessonRollbackTargetError(
                "target revision is already current"
            )

        target = revisions[target_revision]
        try:
            target_bytes = target.markdown.encode("utf-8")
        except UnicodeError as exc:
            raise CanonicalLessonWriteHistoryError(
                "lesson revision snapshot is invalid"
            ) from exc

        changed = target_bytes != current_bytes
        if changed:
            _atomic_replace_exact(path, target_bytes)

        timestamp = occurred_at or datetime.now(timezone.utc).isoformat()
        next_revision = revisions[-1].revision + 1
        rollback = LessonRevision(
            lesson_id=lesson_id,
            revision=next_revision,
            canonical_fingerprint=target.canonical_fingerprint,
            occurred_at=timestamp,
            action="rollback",
            relative_path=relative_path,
            markdown=target.markdown,
            reason=reason,
            rollback_from_revision=target_revision,
        )

        try:
            history_store.append(rollback)
        except LessonRevisionHistoryError as history_exc:
            if changed:
                try:
                    _atomic_replace_exact(path, current_bytes)
                except CanonicalLessonWriteError as recovery_exc:
                    raise CanonicalLessonWriteRecoveryError(
                        "canonical rollback succeeded but history persistence "
                        "and canonical recovery both failed"
                    ) from recovery_exc
            raise CanonicalLessonWriteHistoryError(
                "rollback revision could not be saved; canonical state was recovered"
            ) from history_exc

        if changed:
            invalidate_cache()

        return CanonicalLessonRevisionWriteResult(
            path=path,
            canonical_revision=target.canonical_fingerprint,
            revision=next_revision,
            canonical_changed=changed,
        )
