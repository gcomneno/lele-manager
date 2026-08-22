"""Application workflow for resolving potential contradiction review pairs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias

from lele_manager.adapters.vault_jsonl_refresh import VaultJsonlRefresh
from lele_manager.application.candidate_approval import DerivedRefreshPortError
from lele_manager.application.lesson_writing import (
    CanonicalLessonSnapshot,
    CanonicalLessonWriteAmbiguousError,
    CanonicalLessonWriteError,
    CanonicalLessonWriteNotFoundError,
    CanonicalLessonWriteRecoveryError,
    CanonicalLessonWriteStaleError,
    read_canonical_lesson_snapshot,
    write_revisioned_canonical_lesson_source,
)
from lele_manager.core.canonical_mutation import canonical_mutation_boundary
from lele_manager.core.contradiction_review import (
    AuxiliaryDecision,
    PairIdentity,
    material_fingerprint,
    validate_auxiliary_decision,
)
from lele_manager.core.contradiction_review_store import (
    CONTRADICTION_REVIEW_STORE_FILENAME,
    ContradictionReviewStore,
    ContradictionReviewStoreError,
)
from lele_manager.core.exact_duplicates import is_exact_duplicate_record
from lele_manager.core.lesson_revision_history import LessonRevisionHistoryStore
from lele_manager.core.lifecycle import (
    LifecycleValidationError,
    validate_supersession_chain,
)
from lele_manager.core.relationships import (
    CanonicalRelationshipType,
    CanonicalRelationships,
    RelationshipValidationError,
    normalize_relationships,
)
from lele_manager.core.vault import find_markdown_paths_by_id
from lele_manager.core.vault_registry import ActiveVaultContext, active_vault_context


CanonicalDecision: TypeAlias = Literal["superseded-by", "corrects", "contradicts"]


class _ReviewStore(Protocol):
    def save_decision(
        self,
        *,
        scope: str,
        left_id: str,
        left_fingerprint: str,
        right_id: str,
        right_fingerprint: str,
        decision: Literal["different-context", "dismissed"],
        note: str | None = None,
    ) -> object: ...


class ContradictionResolutionError(Exception):
    """Base class for controlled contradiction-resolution failures."""


class ContradictionResolutionNotFoundError(ContradictionResolutionError):
    pass


class ContradictionResolutionAmbiguousError(ContradictionResolutionError):
    pass


class ContradictionResolutionStaleError(ContradictionResolutionError):
    pass


class ContradictionResolutionConflictError(ContradictionResolutionError):
    pass


class ContradictionResolutionInvalidError(ContradictionResolutionError):
    pass


class ContradictionResolutionStoreError(ContradictionResolutionError):
    pass


class ContradictionResolutionWriteError(ContradictionResolutionError):
    pass


class ContradictionResolutionRecoveryError(ContradictionResolutionError):
    pass


@dataclass(frozen=True, slots=True)
class AuxiliaryResolutionIntent:
    decision: AuxiliaryDecision
    left_id: str
    right_id: str
    left_fingerprint: str
    right_fingerprint: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class SupersededByResolutionIntent:
    superseded_id: str
    replacement_id: str
    expected_superseded_revision: str


@dataclass(frozen=True, slots=True)
class CorrectsResolutionIntent:
    correcting_id: str
    corrected_id: str
    expected_correcting_revision: str


@dataclass(frozen=True, slots=True)
class ContradictsResolutionIntent:
    source_id: str
    target_id: str
    expected_source_revision: str


CanonicalResolutionIntent: TypeAlias = (
    SupersededByResolutionIntent
    | CorrectsResolutionIntent
    | ContradictsResolutionIntent
)


@dataclass(frozen=True, slots=True)
class AuxiliaryResolutionResult:
    vault_id: str
    pair: PairIdentity
    decision: AuxiliaryDecision
    canonical_success: Literal[False]
    canonical_changed: Literal[False]
    derived_refresh_success: None


@dataclass(frozen=True, slots=True)
class CanonicalResolutionResult:
    vault_id: str
    decision: CanonicalDecision
    mutated_lesson_id: str
    referenced_lesson_id: str
    canonical_success: Literal[True]
    canonical_changed: bool
    derived_refresh_success: bool | None
    partial_success: bool
    canonical_revision: str | None
    revision: int | None
    noop_reason: str | None = None
    refresh_error: str | None = None


@dataclass(frozen=True, slots=True)
class _CanonicalRequest:
    decision: CanonicalDecision
    mutated_id: str
    referenced_id: str
    expected_revision: str
    relation_type: CanonicalRelationshipType | None = None


class ContradictionResolutionService:
    def __init__(
        self,
        *,
        context_resolver: Callable[[], ActiveVaultContext] = active_vault_context,
        review_store: _ReviewStore | None = None,
        refresh: Callable[[ActiveVaultContext], object] | None = None,
    ) -> None:
        self._context_resolver = context_resolver
        self._review_store = review_store
        self._refresh = refresh

    def resolve_auxiliary(
        self,
        intent: AuxiliaryResolutionIntent,
    ) -> AuxiliaryResolutionResult:
        context = self._context_resolver()
        try:
            decision = validate_auxiliary_decision(intent.decision)
            pair = PairIdentity.from_ids(intent.left_id, intent.right_id)
        except ValueError as exc:
            raise ContradictionResolutionInvalidError(
                "auxiliary contradiction-review intent is invalid"
            ) from exc

        with canonical_mutation_boundary():
            left = _read_snapshot(context, intent.left_id)
            right = _read_snapshot(context, intent.right_id)
            expected = _normalized_fingerprints(
                intent.left_id,
                intent.left_fingerprint,
                intent.right_id,
                intent.right_fingerprint,
            )
            current = _normalized_fingerprints(
                left.lesson_id,
                _snapshot_material_fingerprint(left),
                right.lesson_id,
                _snapshot_material_fingerprint(right),
            )
            if current != expected:
                raise ContradictionResolutionStaleError(
                    "contradiction-review material changed since the candidate was loaded"
                )
            current_pair, current_left_fingerprint, current_right_fingerprint = current

            store = self._review_store or _default_review_store(context)
            try:
                store.save_decision(
                    scope=context.vault_id,
                    left_id=current_pair.left_id,
                    left_fingerprint=current_left_fingerprint,
                    right_id=current_pair.right_id,
                    right_fingerprint=current_right_fingerprint,
                    decision=decision,
                    note=intent.note,
                )
            except ContradictionReviewStoreError as exc:
                raise ContradictionResolutionStoreError(
                    "contradiction-review decision could not be saved"
                ) from exc

        return AuxiliaryResolutionResult(
            vault_id=context.vault_id,
            pair=pair,
            decision=decision,
            canonical_success=False,
            canonical_changed=False,
            derived_refresh_success=None,
        )

    def resolve_canonical(
        self,
        intent: CanonicalResolutionIntent,
    ) -> CanonicalResolutionResult:
        context = self._context_resolver()
        request = _canonical_request(intent)
        _validate_revision_token(request.expected_revision)

        with canonical_mutation_boundary():
            mutated = _read_snapshot(context, request.mutated_id)
            referenced = _read_snapshot(context, request.referenced_id)
            _validate_distinct(mutated.lesson_id, referenced.lesson_id)
            _validate_current_revision(
                expected_revision=request.expected_revision,
                current_revision=mutated.canonical_revision,
            )
            _reject_exact_duplicate_pair(mutated, referenced)

            exact = _requested_resolution_tuple(
                request,
                mutated_id=mutated.lesson_id,
                referenced_id=referenced.lesson_id,
            )
            existing = _canonical_resolutions_between(mutated, referenced)
            if existing == {exact}:
                return CanonicalResolutionResult(
                    vault_id=context.vault_id,
                    decision=request.decision,
                    mutated_lesson_id=mutated.lesson_id,
                    referenced_lesson_id=referenced.lesson_id,
                    canonical_success=True,
                    canonical_changed=False,
                    derived_refresh_success=None,
                    partial_success=False,
                    canonical_revision=mutated.canonical_revision,
                    revision=None,
                    noop_reason="already-resolved",
                )
            if existing:
                raise ContradictionResolutionConflictError(
                    "contradiction-review pair is already canonically resolved differently"
                )
            if (
                request.decision == "superseded-by"
                and mutated.superseded_by is not None
                and mutated.superseded_by != referenced.lesson_id
            ):
                raise ContradictionResolutionConflictError(
                    "superseded lesson already has a different canonical replacement"
                )

            if request.decision == "superseded-by":
                _validate_supersession(context, mutated.lesson_id, referenced.lesson_id)
                relationships = mutated.relationships
                superseded_by: str | None = referenced.lesson_id
            else:
                if request.relation_type is None:
                    raise AssertionError("relationship resolution is missing its type")
                relationships = _with_relationship_edge(
                    mutated.relationships,
                    source_id=mutated.lesson_id,
                    relation_type=request.relation_type,
                    target_id=referenced.lesson_id,
                )
                superseded_by = mutated.superseded_by

            topic, source, importance, date = _complete_fields(mutated)
            try:
                write_result = write_revisioned_canonical_lesson_source(
                    vault_dir=context.vault_dir,
                    lesson_id=mutated.lesson_id,
                    expected_revision=request.expected_revision,
                    history_store=LessonRevisionHistoryStore(
                        context.revision_history_path
                    ),
                    body=mutated.text,
                    topic=topic,
                    source=source,
                    importance=importance,
                    tags=mutated.tags,
                    date=date,
                    title=mutated.title,
                    lifecycle=mutated.lifecycle,
                    superseded_by=superseded_by,
                    relationships=relationships,
                    reviewed_at=mutated.reviewed_at,
                    review_interval_days=mutated.review_interval_days,
                    preserve_current_body=True,
                    invalidate_cache=lambda: None,
                    reason=f"contradiction-review:{request.decision}",
                )
            except CanonicalLessonWriteStaleError as exc:
                raise ContradictionResolutionStaleError(
                    "canonical lesson changed since it was loaded"
                ) from exc
            except (RelationshipValidationError, LifecycleValidationError) as exc:
                raise ContradictionResolutionInvalidError(
                    "canonical contradiction resolution is invalid"
                ) from exc
            except CanonicalLessonWriteRecoveryError as exc:
                raise ContradictionResolutionRecoveryError(
                    "canonical contradiction resolution is indeterminate: "
                    "canonical Markdown may have changed after history "
                    "persistence and recovery both failed; do not blindly retry"
                ) from exc
            except CanonicalLessonWriteError as exc:
                raise ContradictionResolutionWriteError(
                    "canonical contradiction resolution could not be written"
                ) from exc

        if not write_result.canonical_changed:
            return CanonicalResolutionResult(
                vault_id=context.vault_id,
                decision=request.decision,
                mutated_lesson_id=request.mutated_id,
                referenced_lesson_id=request.referenced_id,
                canonical_success=True,
                canonical_changed=False,
                derived_refresh_success=None,
                partial_success=False,
                canonical_revision=write_result.canonical_revision,
                revision=write_result.revision,
                noop_reason="already-resolved",
            )

        try:
            self._refresh_context(context)
        except Exception as exc:
            return CanonicalResolutionResult(
                vault_id=context.vault_id,
                decision=request.decision,
                mutated_lesson_id=request.mutated_id,
                referenced_lesson_id=request.referenced_id,
                canonical_success=True,
                canonical_changed=True,
                derived_refresh_success=False,
                partial_success=True,
                canonical_revision=write_result.canonical_revision,
                revision=write_result.revision,
                refresh_error=str(exc),
            )

        return CanonicalResolutionResult(
            vault_id=context.vault_id,
            decision=request.decision,
            mutated_lesson_id=request.mutated_id,
            referenced_lesson_id=request.referenced_id,
            canonical_success=True,
            canonical_changed=True,
            derived_refresh_success=True,
            partial_success=False,
            canonical_revision=write_result.canonical_revision,
            revision=write_result.revision,
        )

    def _refresh_context(self, context: ActiveVaultContext) -> None:
        if self._refresh is not None:
            self._refresh(context)
            return
        try:
            VaultJsonlRefresh(context.vault_dir, context.projection_path).refresh()
        except DerivedRefreshPortError as exc:
            raise RuntimeError("configured refresh failed") from exc


def _default_review_store(context: ActiveVaultContext) -> ContradictionReviewStore:
    return ContradictionReviewStore(
        context.candidates_path.parent / CONTRADICTION_REVIEW_STORE_FILENAME
    )


def _canonical_request(intent: CanonicalResolutionIntent) -> _CanonicalRequest:
    if isinstance(intent, SupersededByResolutionIntent):
        return _CanonicalRequest(
            decision="superseded-by",
            mutated_id=intent.superseded_id,
            referenced_id=intent.replacement_id,
            expected_revision=intent.expected_superseded_revision,
        )
    if isinstance(intent, CorrectsResolutionIntent):
        return _CanonicalRequest(
            decision="corrects",
            mutated_id=intent.correcting_id,
            referenced_id=intent.corrected_id,
            expected_revision=intent.expected_correcting_revision,
            relation_type="corrects",
        )
    return _CanonicalRequest(
        decision="contradicts",
        mutated_id=intent.source_id,
        referenced_id=intent.target_id,
        expected_revision=intent.expected_source_revision,
        relation_type="contradicts",
    )


def _validate_revision_token(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ContradictionResolutionInvalidError(
            "canonical contradiction resolution requires an expected revision"
        )


def _validate_current_revision(
    *,
    expected_revision: str,
    current_revision: str,
) -> None:
    if expected_revision != current_revision:
        raise ContradictionResolutionStaleError(
            "canonical lesson changed since the contradiction-review candidate was loaded"
        )


def _validate_distinct(left_id: str, right_id: str) -> None:
    if left_id == right_id:
        raise ContradictionResolutionInvalidError(
            "canonical contradiction resolution requires two distinct lessons"
        )


def _read_snapshot(
    context: ActiveVaultContext,
    lesson_id: str,
) -> CanonicalLessonSnapshot:
    try:
        return read_canonical_lesson_snapshot(
            vault_dir=context.vault_dir,
            lesson_id=lesson_id,
        )
    except CanonicalLessonWriteNotFoundError as exc:
        raise ContradictionResolutionNotFoundError(
            "canonical lesson was not found in the active Vault"
        ) from exc
    except CanonicalLessonWriteAmbiguousError as exc:
        raise ContradictionResolutionAmbiguousError(
            "canonical lesson identity is ambiguous in the active Vault"
        ) from exc


def _snapshot_material_fingerprint(snapshot: CanonicalLessonSnapshot) -> str:
    return material_fingerprint(
        {
            "id": snapshot.lesson_id,
            "text": snapshot.text,
            "title": snapshot.title,
            "topic": snapshot.topic,
            "source": snapshot.source,
            "date": snapshot.date,
            "tags": snapshot.tags,
            "lifecycle": snapshot.lifecycle,
            "superseded_by": snapshot.superseded_by,
            "relationships": snapshot.relationships,
        }
    )


def _reject_exact_duplicate_pair(
    left: CanonicalLessonSnapshot,
    right: CanonicalLessonSnapshot,
) -> None:
    if is_exact_duplicate_record(
        {"id": left.lesson_id, "text": left.text},
        {"id": right.lesson_id, "text": right.text},
    ):
        raise ContradictionResolutionInvalidError(
            "exact duplicate lessons are not valid contradiction-review resolutions"
        )


def _normalized_fingerprints(
    left_id: str,
    left_fingerprint: str,
    right_id: str,
    right_fingerprint: str,
) -> tuple[PairIdentity, str, str]:
    pair = PairIdentity.from_ids(left_id, right_id)
    if not left_fingerprint or not right_fingerprint:
        raise ContradictionResolutionStaleError(
            "contradiction-review material fingerprints are required"
        )
    if pair.left_id == left_id.strip():
        return pair, left_fingerprint, right_fingerprint
    return pair, right_fingerprint, left_fingerprint


def _requested_resolution_tuple(
    request: _CanonicalRequest,
    *,
    mutated_id: str,
    referenced_id: str,
) -> tuple[str, str, str]:
    return request.decision, mutated_id, referenced_id


def _canonical_resolutions_between(
    left: CanonicalLessonSnapshot,
    right: CanonicalLessonSnapshot,
) -> set[tuple[str, str, str]]:
    resolutions: set[tuple[str, str, str]] = set()
    ids = {left.lesson_id, right.lesson_id}
    for source, target in ((left, right), (right, left)):
        if source.superseded_by == target.lesson_id:
            resolutions.add(("superseded-by", source.lesson_id, target.lesson_id))
        for relation_type in ("corrects", "contradicts"):
            for related_id in source.relationships.get(relation_type, ()):
                if related_id in ids:
                    resolutions.add(
                        (relation_type, source.lesson_id, related_id)
                    )
    return resolutions


def _with_relationship_edge(
    relationships: Mapping[CanonicalRelationshipType, tuple[str, ...]],
    *,
    source_id: str,
    relation_type: CanonicalRelationshipType,
    target_id: str,
) -> CanonicalRelationships:
    desired: dict[str, list[str]] = {
        key: list(value) for key, value in relationships.items()
    }
    desired.setdefault(relation_type, [])
    if target_id not in desired[relation_type]:
        desired[relation_type].append(target_id)
    return normalize_relationships(desired, lesson_id=source_id)


def _validate_supersession(
    context: ActiveVaultContext,
    lesson_id: str,
    replacement_id: str,
) -> None:
    def resolve(current_id: str) -> str | None:
        matches = find_markdown_paths_by_id(context.vault_dir, current_id)
        if not matches:
            raise ContradictionResolutionNotFoundError(
                "supersession target was not found in the active Vault"
            )
        if len(matches) != 1:
            raise ContradictionResolutionAmbiguousError(
                "supersession target is ambiguous in the active Vault"
            )
        snapshot = read_canonical_lesson_snapshot(
            vault_dir=context.vault_dir,
            lesson_id=current_id,
        )
        return snapshot.superseded_by

    try:
        validate_supersession_chain(
            lesson_id=lesson_id,
            superseded_by=replacement_id,
            resolve_superseded_by=resolve,
        )
    except LifecycleValidationError as exc:
        raise ContradictionResolutionInvalidError(
            "superseded-by resolution would create an invalid supersession"
        ) from exc


def _complete_fields(snapshot: CanonicalLessonSnapshot) -> tuple[str, str, int, str]:
    if (
        snapshot.topic is None
        or snapshot.source is None
        or snapshot.importance is None
        or snapshot.date is None
    ):
        raise ContradictionResolutionInvalidError(
            "canonical lesson is missing maintained fields required for revision-aware resolution"
        )
    return snapshot.topic, snapshot.source, snapshot.importance, snapshot.date
