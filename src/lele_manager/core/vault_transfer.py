"""Preview-first, registered-Vault canonical lesson transfer workflows.

This module deliberately transfers only canonical Markdown.  Candidate staging
and duplicate-review decisions are per-Vault editorial state and never become
an accidental cross-Vault payload.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Callable, Literal

import pandas as pd

from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.core.duplicate_decisions import material_fingerprint
from lele_manager.core.json_compat import canonical_json
from lele_manager.core.vault_registry import ActiveVaultContext
from lele_manager.core.vault_snapshot import (
    SnapshotPlanStaleError,
    SnapshotTargetError,
    delete_canonical_file,
    read_canonical_markdown_files,
    validate_new_canonical_destination,
    verify_canonical_file,
    write_new_canonical_file,
)
from lele_manager.core.deduplication import (
    DEFAULT_MIN_SCORE,
    DuplicateReport,
    find_duplicates,
)
from lele_manager.ml.features import LessonFeatureExtractor


TRANSFER_SEMANTICS_VERSION = 2
Operation = Literal["merge", "copy", "move"]
Classification = Literal[
    "new", "identical", "already_present", "same_id", "path_conflict", "likely_duplicate",
]
Resolution = Literal["transfer", "keep_destination", "skip"]


class VaultTransferError(RuntimeError):
    code = "vault_transfer_invalid"


class VaultTransferPlanStaleError(VaultTransferError):
    code = "vault_transfer_plan_stale"


class VaultTransferConflictError(VaultTransferError):
    code = "vault_transfer_conflict"


@dataclass(frozen=True)
class _Lesson:
    lesson_id: str
    relative_path: str
    raw: bytes
    fingerprint: str
    record: dict[str, object]


@dataclass(frozen=True)
class TransferItemPreview:
    lesson_id: str
    source_path: str
    source_sha256: str
    destination_path: str
    destination_sha256: str | None
    classification: Classification
    resolution: Resolution | None
    duplicate_lesson_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransferPreview:
    plan_digest: str
    operation: Operation
    source_vault_id: str
    source_name: str
    source_path: str
    destination_vault_id: str
    destination_name: str
    destination_path: str
    items: tuple[TransferItemPreview, ...]


@dataclass(frozen=True)
class TransferItemResult:
    lesson_id: str
    source_path: str
    destination_path: str
    outcome: str
    destination_canonical: str
    destination_derived: str
    source_canonical: str
    source_derived: str


@dataclass(frozen=True)
class TransferResult:
    preview: TransferPreview
    items: tuple[TransferItemResult, ...]
    destination_derived_reconciled: bool | None
    destination_derived_error: str | None
    source_derived_reconciled: bool | None
    source_derived_error: str | None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lesson_record(lesson_id: str, relative_path: str, raw: bytes) -> dict[str, object]:
    try:
        frontmatter, body = parse_markdown_with_frontmatter(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise VaultTransferError("canonical Markdown could not be read as a lesson") from exc
    actual_id = frontmatter.get("id")
    if actual_id is not None and (not isinstance(actual_id, str) or not actual_id.strip()):
        raise VaultTransferError("canonical lesson has an invalid stable ID")
    return {
        "id": actual_id.strip() if isinstance(actual_id, str) else relative_path[:-3],
        "path": relative_path,
        "text": body,
        "title": frontmatter.get("title"),
        "topic": frontmatter.get("topic"),
        "source": frontmatter.get("source"),
        "importance": frontmatter.get("importance"),
        "tags": frontmatter.get("tags"),
        "date": frontmatter.get("date"),
    }


def _lessons(context: ActiveVaultContext) -> dict[str, _Lesson]:
    files = read_canonical_markdown_files(context.vault_dir)
    result: dict[str, _Lesson] = {}
    for relative_path, raw in files.items():
        record = _lesson_record("", relative_path, raw)
        lesson_id = str(record["id"])
        if lesson_id in result:
            raise VaultTransferError("canonical lesson stable ID is ambiguous")
        result[lesson_id] = _Lesson(lesson_id, relative_path, raw, material_fingerprint(record), record)
    return result


def list_transferable_lessons(context: ActiveVaultContext) -> tuple[tuple[str, str], ...]:
    """List the explicit canonical selection set for one registered source."""
    return tuple((item.lesson_id, item.relative_path) for item in sorted(_lessons(context).values(), key=lambda value: value.lesson_id))


def _context_value(context: ActiveVaultContext) -> dict[str, str]:
    return {
        "id": context.vault_id, "name": context.display_name, "vault": str(context.vault_dir),
        "projection": str(context.projection_path), "candidates": str(context.candidates_path),
        "model": str(context.topic_model_path), "decision_scope": context.duplicate_decision_scope,
    }


def _state(lessons: dict[str, _Lesson]) -> list[dict[str, str]]:
    return [
        {"id": item.lesson_id, "path": item.relative_path, "sha256": _sha(item.raw), "fingerprint": item.fingerprint}
        for item in sorted(lessons.values(), key=lambda value: value.lesson_id)
    ]


def _source_duplicate_ids(report: DuplicateReport) -> tuple[str, ...]:
    ids: set[str] = set()
    for pair in report.pairs:
        if pair.left_position == 0:
            ids.add(pair.right_id)
        elif pair.right_position == 0:
            ids.add(pair.left_id)
    return tuple(sorted(ids))


def _likely_duplicate(source: _Lesson, destination: dict[str, _Lesson]) -> tuple[str, ...]:
    if not destination:
        return ()
    frame = pd.DataFrame([source.record, *(item.record for item in destination.values())])

    # Exact #184 semantics do not depend on a fitted feature pipeline and must
    # survive cases where the maintained default vectorizer cannot build a
    # vocabulary for near-duplicate analysis.
    exact = _source_duplicate_ids(find_duplicates(frame, exact_only=True))
    if exact:
        return exact

    try:
        extractor = LessonFeatureExtractor()
        matrix = extractor.fit(frame).transform(frame)
        report = find_duplicates(
            frame,
            feature_matrix=matrix,
            min_score=DEFAULT_MIN_SCORE,
        )
    except (ValueError, TypeError):
        return ()
    return _source_duplicate_ids(report)


def _classify(source: _Lesson, destination: dict[str, _Lesson], destination_paths: dict[str, _Lesson]) -> tuple[Classification, tuple[str, ...]]:
    """Classify canonical identity before semantic similarity.

    Material fingerprints intentionally do not participate in canonical
    equivalence: MOVE safety is based on exact maintained Markdown bytes.
    """
    by_path = destination_paths.get(source.relative_path)
    by_id = destination.get(source.lesson_id)
    if by_path is not None and by_path.raw == source.raw:
        return "identical", ()
    if by_id is not None:
        if by_id.raw == source.raw:
            return "already_present", ()
        return "same_id", ()
    if by_path is not None:
        return "path_conflict", ()
    likely = _likely_duplicate(source, destination)
    if likely:
        return "likely_duplicate", likely
    return "new", ()


def _preview_digest(
    operation: Operation, source: ActiveVaultContext, destination: ActiveVaultContext,
    source_state: dict[str, _Lesson], destination_state: dict[str, _Lesson], items: tuple[TransferItemPreview, ...],
) -> str:
    value = {
        "transfer_semantics_version": TRANSFER_SEMANTICS_VERSION, "operation": operation,
        "source_context": _context_value(source), "destination_context": _context_value(destination),
        "source_state": _state(source_state), "destination_state": _state(destination_state),
        "items": [item.__dict__ | {"duplicate_lesson_ids": list(item.duplicate_lesson_ids)} for item in items],
    }
    return _sha((canonical_json(value) + "\n").encode("utf-8"))


def preview_transfer(
    *, operation: Operation, source: ActiveVaultContext, destination: ActiveVaultContext,
    selections: tuple[tuple[str, Resolution | None], ...],
) -> TransferPreview:
    if operation not in ("merge", "copy", "move"):
        raise VaultTransferError("operation must be merge, copy, or move")
    if source.vault_id == destination.vault_id:
        raise VaultTransferError("source and destination Vaults must be distinct")
    if not selections or len({item[0] for item in selections}) != len(selections):
        raise VaultTransferError("selected lesson IDs must be explicit and unique")
    source_state, destination_state = _lessons(source), _lessons(destination)
    destination_paths = {item.relative_path: item for item in destination_state.values()}
    items: list[TransferItemPreview] = []
    for lesson_id, requested_resolution in sorted(selections):
        selected = source_state.get(lesson_id)
        if selected is None:
            raise VaultTransferError("selected canonical lesson was not found in the source Vault")
        classification, duplicate_ids = _classify(selected, destination_state, destination_paths)
        if classification == "new":
            resolution: Resolution | None = "transfer" if requested_resolution is None else requested_resolution
            if resolution != "transfer":
                raise VaultTransferError("a new lesson can only use the transfer resolution")
        elif classification in ("identical", "already_present"):
            resolution = "keep_destination" if requested_resolution is None else requested_resolution
            if resolution not in ("keep_destination", "skip"):
                raise VaultTransferError("an already present lesson cannot overwrite the destination")
        else:
            resolution = requested_resolution
            if resolution not in ("keep_destination", "skip", None):
                raise VaultTransferError("conflicts require keep destination or skip")
        by_id = destination_state.get(selected.lesson_id)
        by_path = destination_paths.get(selected.relative_path)
        destination_target = by_id if classification in ("same_id", "already_present") else by_path
        destination_path = destination_target.relative_path if destination_target is not None else selected.relative_path
        items.append(TransferItemPreview(
            lesson_id, selected.relative_path, _sha(selected.raw), destination_path,
            _sha(destination_target.raw) if destination_target is not None else None,
            classification, resolution, duplicate_ids,
        ))
    frozen = tuple(items)
    return TransferPreview(
        _preview_digest(operation, source, destination, source_state, destination_state, frozen), operation,
        source.vault_id, source.display_name, str(source.vault_dir), destination.vault_id,
        destination.display_name, str(destination.vault_dir), frozen,
    )


def execute_transfer(
    *, operation: Operation, source: ActiveVaultContext, destination: ActiveVaultContext,
    selections: tuple[tuple[str, Resolution | None], ...], plan_digest: str,
    resolve_source: Callable[[], ActiveVaultContext], resolve_destination: Callable[[], ActiveVaultContext],
    reconcile_destination: Callable[[ActiveVaultContext], None], reconcile_source: Callable[[ActiveVaultContext], None],
) -> TransferResult:
    """Revalidate a stateless plan, then apply destination-first semantics."""
    current = preview_transfer(operation=operation, source=source, destination=destination, selections=selections)
    if current.plan_digest != plan_digest:
        raise VaultTransferPlanStaleError("source, destination, selection, or resolution changed after preview")
    final_source, final_destination = resolve_source(), resolve_destination()
    if final_source != source or final_destination != destination:
        raise VaultTransferPlanStaleError("selected registered Vault context changed after preview")
    if any(item.resolution is None for item in current.items):
        raise VaultTransferConflictError("all transfer conflicts need an explicit resolution")

    source_state, destination_state = _lessons(source), _lessons(destination)

    # The registered contexts are resolved between the first stateless
    # recomputation and this second canonical read. Refuse any state that
    # changed in that window before the first planned mutation begins.
    if (
        _preview_digest(
            operation,
            source,
            destination,
            source_state,
            destination_state,
            current.items,
        )
        != current.plan_digest
    ):
        raise VaultTransferPlanStaleError(
            "source or destination canonical state changed during execution preflight"
        )

    destination_paths = {
        item.relative_path: item for item in destination_state.values()
    }

    # Read-only preflight. The actual create still refuses a late collision,
    # and MOVE re-verifies exact destination bytes before source deletion.
    for item in current.items:
        selected = source_state[item.lesson_id]
        if (
            selected.relative_path != item.source_path
            or _sha(selected.raw) != item.source_sha256
        ):
            raise VaultTransferPlanStaleError(
                "selected source canonical lesson changed after preview"
            )

        if item.resolution == "transfer":
            if selected.relative_path in destination_paths:
                raise VaultTransferPlanStaleError(
                    "destination path changed after preview"
                )
            validate_new_canonical_destination(
                destination.vault_dir,
                selected.relative_path,
            )
        elif (
            item.resolution == "keep_destination"
            and item.classification in ("identical", "already_present")
        ):
            try:
                verify_canonical_file(
                    destination.vault_dir,
                    item.destination_path,
                    selected.raw,
                )
            except (SnapshotPlanStaleError, SnapshotTargetError) as exc:
                raise VaultTransferPlanStaleError(
                    "exact destination canonical lesson changed after preview"
                ) from exc

    results: list[TransferItemResult] = []
    destination_written: list[int] = []
    move_safe: list[tuple[int, _Lesson, str]] = []

    for item in current.items:
        selected = source_state[item.lesson_id]
        if item.resolution == "skip" or (
            item.resolution == "keep_destination"
            and item.classification not in ("identical", "already_present")
        ):
            results.append(TransferItemResult(
                item.lesson_id, item.source_path, item.destination_path,
                "skipped_by_resolution", "not_attempted", "not_needed",
                "unchanged", "not_needed",
            ))
            continue

        if item.resolution == "keep_destination":
            # Only exact canonical identity reaches this branch. It is a no-op
            # for destination derived state, but may safely support MOVE.
            results.append(TransferItemResult(
                item.lesson_id, item.source_path, item.destination_path,
                "destination_already_exact", "already_exact", "not_needed",
                "unchanged", "not_needed",
            ))
            move_safe.append((len(results) - 1, selected, item.destination_path))
            continue

        try:
            write_new_canonical_file(destination.vault_dir, selected.relative_path, selected.raw)
        except SnapshotTargetError:
            results.append(TransferItemResult(
                item.lesson_id, item.source_path, item.destination_path,
                "destination_write_failed", "failed", "not_attempted",
                "unchanged", "not_needed",
            ))
        else:
            results.append(TransferItemResult(
                item.lesson_id, item.source_path, item.destination_path,
                "destination_written", "written", "pending",
                "unchanged", "not_needed",
            ))
            index = len(results) - 1
            destination_written.append(index)
            move_safe.append((index, selected, selected.relative_path))

    destination_error: str | None = None
    destination_reconciled: bool | None = None
    if destination_written:
        try:
            reconcile_destination(destination)
            destination_reconciled = True
        except Exception:
            destination_reconciled = False
            destination_error = "Destination derived reconciliation failed; run a maintained refresh."
        for index in destination_written:
            results[index] = replace(
                results[index],
                destination_derived="reconciled" if destination_reconciled else "failed",
            )

    deleted: list[int] = []
    if operation == "move":
        for index, selected, destination_path in move_safe:
            # Destination canonical bytes are verified immediately before the
            # destructive source step. This applies to both newly written and
            # pre-existing exact destination lessons.
            try:
                verify_canonical_file(destination.vault_dir, destination_path, selected.raw)
            except (SnapshotPlanStaleError, SnapshotTargetError):
                results[index] = replace(
                    results[index],
                    outcome="move_destination_verification_failed",
                    destination_canonical="verification_failed",
                    source_canonical="unchanged",
                    source_derived="not_needed",
                )
                continue
            try:
                delete_canonical_file(source.vault_dir, selected.relative_path, selected.raw)
            except (SnapshotPlanStaleError, SnapshotTargetError):
                results[index] = replace(
                    results[index],
                    outcome="move_source_delete_failed",
                    source_canonical="failed",
                    source_derived="not_needed",
                )
            else:
                deleted.append(index)
                results[index] = replace(
                    results[index],
                    outcome="moved",
                    source_canonical="deleted",
                    source_derived="pending",
                )

    source_error: str | None = None
    source_reconciled: bool | None = None
    if deleted:
        try:
            reconcile_source(source)
            source_reconciled = True
        except Exception:
            source_reconciled = False
            source_error = "Source derived reconciliation failed; run a maintained refresh."
        for index in deleted:
            results[index] = replace(
                results[index],
                source_derived="reconciled" if source_reconciled else "failed",
            )

    return TransferResult(
        current,
        tuple(results),
        destination_reconciled,
        destination_error,
        source_reconciled,
        source_error,
    )
