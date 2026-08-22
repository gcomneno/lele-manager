from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from lele_manager.application.contradiction_resolution import (
    AuxiliaryResolutionIntent,
    ContradictionResolutionAmbiguousError,
    ContradictionResolutionConflictError,
    ContradictionResolutionInvalidError,
    ContradictionResolutionNotFoundError,
    ContradictionResolutionRecoveryError,
    ContradictionResolutionService,
    ContradictionResolutionStaleError,
    ContradictionResolutionStoreError,
    ContradictionResolutionWriteError,
    ContradictsResolutionIntent,
    CorrectsResolutionIntent,
    SupersededByResolutionIntent,
)
from lele_manager.application.lesson_writing import (
    CanonicalLessonWriteRecoveryError,
    read_canonical_lesson_revision,
    read_canonical_lesson_snapshot,
)
from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.core.contradiction_review import material_fingerprint
from lele_manager.core.contradiction_review_store import (
    ContradictionReviewStore,
    ContradictionReviewStoreError,
)
from lele_manager.core.lesson_revision_history import LessonRevisionHistoryStore
from lele_manager.core.vault import find_markdown_paths_by_id, write_lesson_markdown
from lele_manager.core.vault_registry import ActiveVaultContext


def _context(tmp_path: Path, *, vault_id: str = "11111111-1111-4111-8111-111111111111") -> ActiveVaultContext:
    vault = tmp_path / "vault"
    return ActiveVaultContext(
        vault_id=vault_id,
        display_name="Test Vault",
        vault_dir=vault,
        projection_path=tmp_path / "data" / "vaults" / vault_id / "lessons.jsonl",
        candidates_path=tmp_path / "data" / "vaults" / vault_id / "candidates.json",
        topic_model_path=tmp_path / "cache" / "vaults" / vault_id / "topic_model.joblib",
        duplicate_decision_scope=vault_id,
    )


def _service(
    context: ActiveVaultContext,
    *,
    store: ContradictionReviewStore | None = None,
    refresh: Callable[[ActiveVaultContext], object] | None = None,
) -> ContradictionResolutionService:
    return ContradictionResolutionService(
        context_resolver=lambda: context,
        review_store=store,
        refresh=refresh,
    )


def _write(
    context: ActiveVaultContext,
    lesson_id: str,
    *,
    body: str | None = None,
    title: str | None = None,
    relationships: dict[str, list[str]] | None = None,
    superseded_by: str | None = None,
    lifecycle: str = "active",
    provenance: dict[str, object] | None = None,
) -> Path:
    topic = lesson_id.split("/", 1)[0]
    return write_lesson_markdown(
        context.vault_dir,
        lesson_id=lesson_id,
        body=body or f"Use the stable guidance for {lesson_id}.",
        topic=topic,
        source="note",
        importance=3,
        tags=["review", topic],
        date="2026-08-22",
        title=title or lesson_id.rsplit("/", 1)[-1].title(),
        relationships=relationships,
        superseded_by=superseded_by,
        lifecycle=lifecycle,
        provenance=provenance,
    )


def _path(context: ActiveVaultContext, lesson_id: str) -> Path:
    matches = find_markdown_paths_by_id(context.vault_dir, lesson_id)
    assert len(matches) == 1
    return matches[0]


def _frontmatter_and_body(context: ActiveVaultContext, lesson_id: str) -> tuple[dict[str, Any], str]:
    frontmatter, body = parse_markdown_with_frontmatter(_path(context, lesson_id).read_text(encoding="utf-8"))
    return dict(frontmatter), body


def _fingerprint(context: ActiveVaultContext, lesson_id: str) -> str:
    snapshot = read_canonical_lesson_snapshot(vault_dir=context.vault_dir, lesson_id=lesson_id)
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


def _revision(context: ActiveVaultContext, lesson_id: str) -> str:
    return read_canonical_lesson_revision(vault_dir=context.vault_dir, lesson_id=lesson_id).canonical_revision


@pytest.mark.parametrize("decision", ["different-context", "dismissed"])
def test_auxiliary_resolution_persists_only_auxiliary_decision(decision: str, tmp_path: Path) -> None:
    context = _context(tmp_path)
    left = _write(context, "alpha/left")
    right = _write(context, "alpha/right")
    before = {left: left.read_bytes(), right: right.read_bytes()}
    store = ContradictionReviewStore(tmp_path / "contradiction-review-decisions.json")
    refreshes = 0

    def refresh(_context: ActiveVaultContext) -> None:
        nonlocal refreshes
        refreshes += 1

    result = _service(context, store=store, refresh=refresh).resolve_auxiliary(
        AuxiliaryResolutionIntent(
            decision=decision,  # type: ignore[arg-type]
            left_id="alpha/left",
            right_id="alpha/right",
            left_fingerprint=_fingerprint(context, "alpha/left"),
            right_fingerprint=_fingerprint(context, "alpha/right"),
            note="not the same context",
        )
    )

    assert result.vault_id == context.vault_id
    assert result.decision == decision
    assert result.canonical_success is False
    assert result.derived_refresh_success is None
    assert left.read_bytes() == before[left]
    assert right.read_bytes() == before[right]
    assert LessonRevisionHistoryStore(context.revision_history_path).list("alpha/left") == ()
    assert LessonRevisionHistoryStore(context.revision_history_path).list("alpha/right") == ()
    assert refreshes == 0
    assert store.is_suppressed(
        scope=context.vault_id,
        left_id="alpha/right",
        left_fingerprint=_fingerprint(context, "alpha/right"),
        right_id="alpha/left",
        right_fingerprint=_fingerprint(context, "alpha/left"),
    )


def test_auxiliary_resolution_rejects_stale_material_and_uses_active_vault_scope(tmp_path: Path) -> None:
    context = _context(tmp_path, vault_id="22222222-2222-4222-8222-222222222222")
    _write(context, "alpha/left")
    _write(context, "alpha/right")
    store = ContradictionReviewStore(tmp_path / "store.json")
    service = _service(context, store=store)

    with pytest.raises(ContradictionResolutionStaleError):
        service.resolve_auxiliary(
            AuxiliaryResolutionIntent(
                decision="dismissed",
                left_id="alpha/left",
                right_id="alpha/right",
                left_fingerprint="stale",
                right_fingerprint=_fingerprint(context, "alpha/right"),
            )
        )

    service.resolve_auxiliary(
        AuxiliaryResolutionIntent(
            decision="dismissed",
            left_id="alpha/left",
            right_id="alpha/right",
            left_fingerprint=_fingerprint(context, "alpha/left"),
            right_fingerprint=_fingerprint(context, "alpha/right"),
        )
    )
    assert store.is_suppressed(
        scope=context.vault_id,
        left_id="alpha/left",
        left_fingerprint=_fingerprint(context, "alpha/left"),
        right_id="alpha/right",
        right_fingerprint=_fingerprint(context, "alpha/right"),
    )
    assert not store.is_suppressed(
        scope="caller-controlled-scope",
        left_id="alpha/left",
        left_fingerprint=_fingerprint(context, "alpha/left"),
        right_id="alpha/right",
        right_fingerprint=_fingerprint(context, "alpha/right"),
    )


def test_auxiliary_resolution_reversed_orientation_persists_normalized_fingerprints(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    _write(context, "alpha/a", body="Canonical lesson A.")
    _write(context, "alpha/z", body="Canonical lesson Z.")
    store = ContradictionReviewStore(tmp_path / "store.json")
    a_fingerprint = _fingerprint(context, "alpha/a")
    z_fingerprint = _fingerprint(context, "alpha/z")

    _service(context, store=store).resolve_auxiliary(
        AuxiliaryResolutionIntent(
            decision="dismissed",
            left_id="alpha/z",
            right_id="alpha/a",
            left_fingerprint=z_fingerprint,
            right_fingerprint=a_fingerprint,
        )
    )

    data = json.loads(store.path.read_text(encoding="utf-8"))
    entry = data["scopes"][context.vault_id][0]
    assert entry["left_id"] == "alpha/a"
    assert entry["left_fingerprint"] == a_fingerprint
    assert entry["right_id"] == "alpha/z"
    assert entry["right_fingerprint"] == z_fingerprint
    assert store.is_suppressed(
        scope=context.vault_id,
        left_id="alpha/z",
        left_fingerprint=z_fingerprint,
        right_id="alpha/a",
        right_fingerprint=a_fingerprint,
    )


def test_auxiliary_resolution_same_process_canonical_race_cannot_persist_stale_decision(
    tmp_path: Path,
) -> None:
    import threading

    import lele_manager.core.canonical_mutation as mutation

    context = _context(tmp_path)
    left = _write(context, "alpha/left", body="Race boundary left.")
    right = _write(context, "alpha/right", body="Race boundary right.")
    store_path = tmp_path / "store.json"
    attempted: dict[str, bool] = {}

    class RacingStore(ContradictionReviewStore):
        def save_decision(self, **kwargs: object) -> object:
            def attempt_canonical_mutation() -> None:
                acquired = mutation._LOCK.acquire(blocking=False)  # noqa: SLF001
                attempted["acquired"] = acquired
                if not acquired:
                    return
                try:
                    left.write_text("stale race changed markdown", encoding="utf-8")
                finally:
                    mutation._LOCK.release()  # noqa: SLF001

            thread = threading.Thread(target=attempt_canonical_mutation)
            thread.start()
            thread.join()
            return super().save_decision(**kwargs)  # type: ignore[arg-type]

    store = RacingStore(store_path)

    _service(context, store=store).resolve_auxiliary(
        AuxiliaryResolutionIntent(
            decision="dismissed",
            left_id="alpha/left",
            right_id="alpha/right",
            left_fingerprint=_fingerprint(context, "alpha/left"),
            right_fingerprint=_fingerprint(context, "alpha/right"),
        )
    )

    assert attempted == {"acquired": False}
    assert left.read_text(encoding="utf-8") != "stale race changed markdown"
    assert store.is_suppressed(
        scope=context.vault_id,
        left_id="alpha/left",
        left_fingerprint=_fingerprint(context, "alpha/left"),
        right_id="alpha/right",
        right_fingerprint=_fingerprint(context, "alpha/right"),
    )
    assert LessonRevisionHistoryStore(context.revision_history_path).list("alpha/left") == ()
    assert LessonRevisionHistoryStore(context.revision_history_path).list("alpha/right") == ()
    assert right.exists()


@pytest.mark.parametrize("store_case", ["corrupt", "save-failure"])
def test_auxiliary_resolution_store_failure_is_typed_without_canonical_or_refresh(
    store_case: str,
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    left = _write(context, "alpha/left", body="Store failure left.")
    right = _write(context, "alpha/right", body="Store failure right.")
    before = {left: left.read_bytes(), right: right.read_bytes()}
    refreshes = 0

    def refresh(_context: ActiveVaultContext) -> None:
        nonlocal refreshes
        refreshes += 1

    if store_case == "corrupt":
        store = ContradictionReviewStore(tmp_path / "store.json")
        store.path.write_text("{not-json", encoding="utf-8")
    else:

        class FailingStore(ContradictionReviewStore):
            def save_decision(self, **kwargs: object) -> object:
                raise ContradictionReviewStoreError("save failed")

        store = FailingStore(tmp_path / "store.json")

    with pytest.raises(ContradictionResolutionStoreError):
        _service(context, store=store, refresh=refresh).resolve_auxiliary(
            AuxiliaryResolutionIntent(
                decision="dismissed",
                left_id="alpha/left",
                right_id="alpha/right",
                left_fingerprint=_fingerprint(context, "alpha/left"),
                right_fingerprint=_fingerprint(context, "alpha/right"),
            )
        )

    assert left.read_bytes() == before[left]
    assert right.read_bytes() == before[right]
    assert refreshes == 0


def test_auxiliary_resolution_fails_closed_for_missing_and_ambiguous_ids(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write(context, "alpha/left")
    service = _service(context)

    with pytest.raises(ContradictionResolutionNotFoundError):
        service.resolve_auxiliary(
            AuxiliaryResolutionIntent(
                decision="dismissed",
                left_id="alpha/left",
                right_id="alpha/missing",
                left_fingerprint=_fingerprint(context, "alpha/left"),
                right_fingerprint="missing",
            )
        )

    first = context.vault_dir / "one.md"
    second = context.vault_dir / "two.md"
    first.write_text("---\nid: alpha/ambiguous\n---\nfirst\n", encoding="utf-8")
    second.write_text("---\nid: alpha/ambiguous\n---\nsecond\n", encoding="utf-8")
    with pytest.raises(ContradictionResolutionAmbiguousError):
        service.resolve_auxiliary(
            AuxiliaryResolutionIntent(
                decision="dismissed",
                left_id="alpha/left",
                right_id="alpha/ambiguous",
                left_fingerprint=_fingerprint(context, "alpha/left"),
                right_fingerprint="ambiguous",
            )
        )


@pytest.mark.parametrize(
    ("relation", "intent_factory"),
    [
        (
            "corrects",
            lambda revision: CorrectsResolutionIntent(
                correcting_id="alpha/source",
                corrected_id="alpha/target",
                expected_correcting_revision=revision,
            ),
        ),
        (
            "contradicts",
            lambda revision: ContradictsResolutionIntent(
                source_id="alpha/source",
                target_id="alpha/target",
                expected_source_revision=revision,
            ),
        ),
    ],
)
def test_relationship_resolution_mutates_only_source_direction(
    relation: str,
    intent_factory: Callable[[str], CorrectsResolutionIntent | ContradictsResolutionIntent],
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    source = _write(
        context,
        "alpha/source",
        body="Line one.\n\nLine two.",
        relationships={"extends": ["alpha/base"]},
        provenance={"candidate_id": "sha256:source", "source_kind": "test"},
        lifecycle="review-needed",
    )
    target = _write(context, "alpha/target", relationships={"see-also": ["alpha/other"]})
    source_before = source.read_bytes()
    target_before = target.read_bytes()
    refreshes = 0

    def refresh(_context: ActiveVaultContext) -> None:
        nonlocal refreshes
        refreshes += 1

    result = _service(context, refresh=refresh).resolve_canonical(
        intent_factory(_revision(context, "alpha/source"))
    )

    source_frontmatter, source_body = _frontmatter_and_body(context, "alpha/source")
    target_frontmatter, _ = _frontmatter_and_body(context, "alpha/target")
    assert result.canonical_success is True
    assert result.canonical_changed is True
    assert result.derived_refresh_success is True
    assert result.partial_success is False
    assert result.mutated_lesson_id == "alpha/source"
    assert relation in source_frontmatter["relationships"]
    assert source_frontmatter["relationships"][relation] == ["alpha/target"]
    assert source_frontmatter["relationships"]["extends"] == ["alpha/base"]
    assert relation not in target_frontmatter["relationships"]
    assert target.read_bytes() == target_before
    assert source.read_bytes() != source_before
    assert source_body == "Line one.\n\nLine two."
    assert source_frontmatter["provenance"] == {"candidate_id": "sha256:source", "source_kind": "test"}
    assert source_frontmatter["lifecycle"] == "review-needed"
    assert refreshes == 1
    assert [item.action for item in LessonRevisionHistoryStore(context.revision_history_path).list("alpha/source")] == [
        "baseline",
        "edit",
    ]


@pytest.mark.parametrize(
    ("relation", "intent_factory"),
    [
        (
            "corrects",
            lambda revision: CorrectsResolutionIntent(
                correcting_id="alpha/source",
                corrected_id="alpha/target",
                expected_correcting_revision=revision,
            ),
        ),
        (
            "contradicts",
            lambda revision: ContradictsResolutionIntent(
                source_id="alpha/source",
                target_id="alpha/target",
                expected_source_revision=revision,
            ),
        ),
    ],
)
def test_existing_relationship_edge_is_noop_without_history_or_refresh(
    relation: str,
    intent_factory: Callable[[str], CorrectsResolutionIntent | ContradictsResolutionIntent],
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    source = _write(context, "alpha/source", relationships={relation: ["alpha/target"]})
    target = _write(context, "alpha/target")
    before = {source: source.read_bytes(), target: target.read_bytes()}
    refreshes = 0

    def refresh(_context: ActiveVaultContext) -> None:
        nonlocal refreshes
        refreshes += 1

    result = _service(context, refresh=refresh).resolve_canonical(
        intent_factory(_revision(context, "alpha/source"))
    )

    assert result.canonical_success is True
    assert result.canonical_changed is False
    assert result.noop_reason == "already-resolved"
    assert source.read_bytes() == before[source]
    assert target.read_bytes() == before[target]
    assert LessonRevisionHistoryStore(context.revision_history_path).list("alpha/source") == ()
    assert refreshes == 0


@pytest.mark.parametrize(
    ("label", "intent_factory", "relationships", "superseded_by"),
    [
        (
            "corrects",
            lambda revision: CorrectsResolutionIntent(
                correcting_id="alpha/source",
                corrected_id="alpha/target",
                expected_correcting_revision=revision,
            ),
            {"corrects": ["alpha/target"]},
            None,
        ),
        (
            "contradicts",
            lambda revision: ContradictsResolutionIntent(
                source_id="alpha/source",
                target_id="alpha/target",
                expected_source_revision=revision,
            ),
            {"contradicts": ["alpha/target"]},
            None,
        ),
        (
            "superseded-by",
            lambda revision: SupersededByResolutionIntent(
                superseded_id="alpha/source",
                replacement_id="alpha/target",
                expected_superseded_revision=revision,
            ),
            None,
            "alpha/target",
        ),
    ],
)
def test_existing_exact_canonical_resolution_with_stale_revision_fails_closed(
    label: str,
    intent_factory: Callable[
        [str],
        CorrectsResolutionIntent | ContradictsResolutionIntent | SupersededByResolutionIntent,
    ],
    relationships: dict[str, list[str]] | None,
    superseded_by: str | None,
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    source = _write(
        context,
        "alpha/source",
        relationships=relationships,
        superseded_by=superseded_by,
    )
    _write(context, "alpha/target")
    stale_revision = _revision(context, "alpha/source")
    source.write_text(
        source.read_text(encoding="utf-8").replace("stable guidance", f"{label} changed guidance"),
        encoding="utf-8",
    )

    with pytest.raises(ContradictionResolutionStaleError):
        _service(context).resolve_canonical(intent_factory(stale_revision))


def test_existing_exact_resolution_plus_conflicting_pair_resolution_fails_closed(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    _write(
        context,
        "alpha/source",
        relationships={
            "corrects": ["alpha/target"],
            "contradicts": ["alpha/target"],
        },
    )
    _write(context, "alpha/target")

    with pytest.raises(ContradictionResolutionConflictError):
        _service(context).resolve_canonical(
            CorrectsResolutionIntent(
                correcting_id="alpha/source",
                corrected_id="alpha/target",
                expected_correcting_revision=_revision(context, "alpha/source"),
            )
        )


@pytest.mark.parametrize(
    "intent_factory",
    [
        lambda revision: SupersededByResolutionIntent(
            superseded_id="alpha/source",
            replacement_id="alpha/target",
            expected_superseded_revision=revision,
        ),
        lambda revision: CorrectsResolutionIntent(
            correcting_id="alpha/source",
            corrected_id="alpha/target",
            expected_correcting_revision=revision,
        ),
        lambda revision: ContradictsResolutionIntent(
            source_id="alpha/source",
            target_id="alpha/target",
            expected_source_revision=revision,
        ),
    ],
)
def test_canonical_resolution_rejects_exact_duplicate_pair_for_all_intents(
    intent_factory: Callable[
        [str],
        SupersededByResolutionIntent | CorrectsResolutionIntent | ContradictsResolutionIntent,
    ],
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    _write(context, "alpha/source", body="\n Same exact lesson. \n")
    _write(context, "alpha/target", body="Same exact lesson.")

    with pytest.raises(ContradictionResolutionInvalidError):
        _service(context).resolve_canonical(
            intent_factory(_revision(context, "alpha/source"))
        )


@pytest.mark.parametrize(
    "intent",
    [
        CorrectsResolutionIntent(
            correcting_id="alpha/source",
            corrected_id="alpha/source",
            expected_correcting_revision="sha256:any",
        ),
        ContradictsResolutionIntent(
            source_id="alpha/source",
            target_id="alpha/source",
            expected_source_revision="sha256:any",
        ),
    ],
)
def test_relationship_resolution_rejects_self_relation(intent: CorrectsResolutionIntent | ContradictsResolutionIntent, tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write(context, "alpha/source")

    with pytest.raises(ContradictionResolutionInvalidError):
        _service(context).resolve_canonical(intent)


def test_relationship_resolution_rejects_stale_missing_and_ambiguous_target(tmp_path: Path) -> None:
    context = _context(tmp_path)
    source = _write(context, "alpha/source")
    _write(context, "alpha/target")
    stale = _revision(context, "alpha/source")
    source.write_text(source.read_text(encoding="utf-8").replace("Use the stable", "Use changed"), encoding="utf-8")

    with pytest.raises(ContradictionResolutionStaleError):
        _service(context).resolve_canonical(
            CorrectsResolutionIntent(
                correcting_id="alpha/source",
                corrected_id="alpha/target",
                expected_correcting_revision=stale,
            )
        )

    current = _revision(context, "alpha/source")
    with pytest.raises(ContradictionResolutionNotFoundError):
        _service(context).resolve_canonical(
            ContradictsResolutionIntent(
                source_id="alpha/source",
                target_id="alpha/missing",
                expected_source_revision=current,
            )
        )

    (context.vault_dir / "ambiguous-one.md").write_text("---\nid: alpha/ambiguous\n---\none\n", encoding="utf-8")
    (context.vault_dir / "ambiguous-two.md").write_text("---\nid: alpha/ambiguous\n---\ntwo\n", encoding="utf-8")
    with pytest.raises(ContradictionResolutionAmbiguousError):
        _service(context).resolve_canonical(
            ContradictsResolutionIntent(
                source_id="alpha/source",
                target_id="alpha/ambiguous",
                expected_source_revision=current,
            )
        )


def test_superseded_by_resolution_mutates_only_superseded_lesson(tmp_path: Path) -> None:
    context = _context(tmp_path)
    superseded = _write(
        context,
        "alpha/old",
        relationships={"see-also": ["alpha/context"]},
        provenance={"candidate_id": "sha256:old"},
        lifecycle="review-needed",
    )
    replacement = _write(context, "alpha/new")
    superseded_before = superseded.read_bytes()
    replacement_before = replacement.read_bytes()
    refreshes = 0

    def refresh(_context: ActiveVaultContext) -> None:
        nonlocal refreshes
        refreshes += 1

    result = _service(context, refresh=refresh).resolve_canonical(
        SupersededByResolutionIntent(
            superseded_id="alpha/old",
            replacement_id="alpha/new",
            expected_superseded_revision=_revision(context, "alpha/old"),
        )
    )

    frontmatter, body = _frontmatter_and_body(context, "alpha/old")
    assert result.canonical_success is True
    assert result.canonical_changed is True
    assert frontmatter["superseded_by"] == "alpha/new"
    assert "supersedes" not in frontmatter.get("relationships", {})
    assert frontmatter["relationships"]["see-also"] == ["alpha/context"]
    assert frontmatter["provenance"] == {"candidate_id": "sha256:old"}
    assert frontmatter["lifecycle"] == "review-needed"
    assert body.strip() == "Use the stable guidance for alpha/old."
    assert replacement.read_bytes() == replacement_before
    assert superseded.read_bytes() != superseded_before
    assert refreshes == 1


def test_existing_superseded_by_is_noop_and_conflicting_existing_supersession_fails(tmp_path: Path) -> None:
    context = _context(tmp_path)
    old = _write(context, "alpha/old", superseded_by="alpha/new")
    new = _write(context, "alpha/new")
    other = _write(context, "alpha/other")
    before = {old: old.read_bytes(), new: new.read_bytes(), other: other.read_bytes()}
    refreshes = 0

    def refresh(_context: ActiveVaultContext) -> None:
        nonlocal refreshes
        refreshes += 1

    result = _service(context, refresh=refresh).resolve_canonical(
        SupersededByResolutionIntent(
            superseded_id="alpha/old",
            replacement_id="alpha/new",
            expected_superseded_revision=_revision(context, "alpha/old"),
        )
    )
    assert result.canonical_changed is False
    assert result.noop_reason == "already-resolved"
    assert LessonRevisionHistoryStore(context.revision_history_path).list("alpha/old") == ()
    assert refreshes == 0
    assert old.read_bytes() == before[old]

    with pytest.raises(ContradictionResolutionConflictError):
        _service(context).resolve_canonical(
            SupersededByResolutionIntent(
                superseded_id="alpha/old",
                replacement_id="alpha/other",
                expected_superseded_revision=_revision(context, "alpha/old"),
            )
        )
    assert old.read_bytes() == before[old]


def test_supersession_rejects_cycle_stale_missing_ambiguous_and_preserves_lifecycle(tmp_path: Path) -> None:
    context = _context(tmp_path)
    a = _write(context, "alpha/a", lifecycle="review-needed")
    _write(context, "alpha/b", superseded_by="alpha/c")
    _write(context, "alpha/c", superseded_by="alpha/a")
    _write(context, "alpha/d")

    with pytest.raises(ContradictionResolutionInvalidError):
        _service(context).resolve_canonical(
            SupersededByResolutionIntent(
                superseded_id="alpha/a",
                replacement_id="alpha/b",
                expected_superseded_revision=_revision(context, "alpha/a"),
            )
        )
    frontmatter, _ = _frontmatter_and_body(context, "alpha/a")
    assert frontmatter["lifecycle"] == "review-needed"
    assert "superseded_by" not in frontmatter

    stale = _revision(context, "alpha/a")
    a.write_text(a.read_text(encoding="utf-8").replace("Use the stable", "Use changed"), encoding="utf-8")
    with pytest.raises(ContradictionResolutionStaleError):
        _service(context).resolve_canonical(
            SupersededByResolutionIntent(
                superseded_id="alpha/a",
                replacement_id="alpha/d",
                expected_superseded_revision=stale,
            )
        )

    current = _revision(context, "alpha/a")
    with pytest.raises(ContradictionResolutionNotFoundError):
        _service(context).resolve_canonical(
            SupersededByResolutionIntent(
                superseded_id="alpha/a",
                replacement_id="alpha/missing",
                expected_superseded_revision=current,
            )
        )

    (context.vault_dir / "ambiguous-one.md").write_text("---\nid: alpha/ambiguous\n---\none\n", encoding="utf-8")
    (context.vault_dir / "ambiguous-two.md").write_text("---\nid: alpha/ambiguous\n---\ntwo\n", encoding="utf-8")
    with pytest.raises(ContradictionResolutionAmbiguousError):
        _service(context).resolve_canonical(
            SupersededByResolutionIntent(
                superseded_id="alpha/a",
                replacement_id="alpha/ambiguous",
                expected_superseded_revision=current,
            )
        )


def test_candidate_fingerprint_cannot_substitute_for_canonical_revision(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write(context, "alpha/source")
    _write(context, "alpha/target")

    with pytest.raises(ContradictionResolutionStaleError):
        _service(context).resolve_canonical(
            CorrectsResolutionIntent(
                correcting_id="alpha/source",
                corrected_id="alpha/target",
                expected_correcting_revision=_fingerprint(context, "alpha/source"),
            )
        )


def test_current_revision_is_rechecked_at_mutation_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lele_manager.application.contradiction_resolution as resolution

    context = _context(tmp_path)
    source = _write(context, "alpha/source")
    _write(context, "alpha/target")
    revision = _revision(context, "alpha/source")
    original = resolution.write_revisioned_canonical_lesson_source

    def racing_write(**kwargs: object) -> object:
        source.write_text(
            source.read_text(encoding="utf-8").replace("Use the stable", "Race changed"),
            encoding="utf-8",
        )
        return original(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(resolution, "write_revisioned_canonical_lesson_source", racing_write)

    with pytest.raises(ContradictionResolutionStaleError):
        _service(context).resolve_canonical(
            CorrectsResolutionIntent(
                correcting_id="alpha/source",
                corrected_id="alpha/target",
                expected_correcting_revision=revision,
            )
        )


def test_incompatible_canonical_resolution_after_candidate_surfacing_fails_closed(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write(context, "alpha/source")
    _write(context, "alpha/target", relationships={"contradicts": ["alpha/source"]})

    with pytest.raises(ContradictionResolutionConflictError):
        _service(context).resolve_canonical(
            ContradictsResolutionIntent(
                source_id="alpha/source",
                target_id="alpha/target",
                expected_source_revision=_revision(context, "alpha/source"),
            )
        )


def test_canonical_write_recovery_failure_surfaces_indeterminate_do_not_blindly_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lele_manager.application.contradiction_resolution as resolution

    context = _context(tmp_path)
    _write(context, "alpha/source")
    _write(context, "alpha/target")
    store = ContradictionReviewStore(tmp_path / "store.json")
    refreshes = 0

    def recovery_failure(**_kwargs: object) -> object:
        raise CanonicalLessonWriteRecoveryError(
            "canonical write succeeded but recovery failed"
        )

    def refresh(_context: ActiveVaultContext) -> None:
        nonlocal refreshes
        refreshes += 1

    monkeypatch.setattr(
        resolution,
        "write_revisioned_canonical_lesson_source",
        recovery_failure,
    )

    with pytest.raises(
        ContradictionResolutionRecoveryError,
        match="do not blindly retry",
    ) as exc_info:
        _service(context, store=store, refresh=refresh).resolve_canonical(
            ContradictsResolutionIntent(
                source_id="alpha/source",
                target_id="alpha/target",
                expected_source_revision=_revision(context, "alpha/source"),
            )
        )

    assert not isinstance(exc_info.value, ContradictionResolutionWriteError)
    assert not store.path.exists()
    assert refreshes == 0


def test_canonical_success_with_refresh_failure_returns_partial_success_without_retry_or_auxiliary_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lele_manager.application.contradiction_resolution as resolution

    context = _context(tmp_path)
    source = _write(context, "alpha/source")
    _write(context, "alpha/target")
    store = ContradictionReviewStore(tmp_path / "store.json")
    calls = 0
    original = resolution.write_revisioned_canonical_lesson_source

    def counted_write(**kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(**kwargs)  # type: ignore[arg-type]

    def failing_refresh(_context: ActiveVaultContext) -> None:
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(resolution, "write_revisioned_canonical_lesson_source", counted_write)

    result = _service(context, store=store, refresh=failing_refresh).resolve_canonical(
        ContradictsResolutionIntent(
            source_id="alpha/source",
            target_id="alpha/target",
            expected_source_revision=_revision(context, "alpha/source"),
        )
    )

    frontmatter, _ = _frontmatter_and_body(context, "alpha/source")
    assert result.canonical_success is True
    assert result.canonical_changed is True
    assert result.derived_refresh_success is False
    assert result.partial_success is True
    assert result.refresh_error == "refresh failed"
    assert frontmatter["relationships"]["contradicts"] == ["alpha/target"]
    assert [item.action for item in LessonRevisionHistoryStore(context.revision_history_path).list("alpha/source")] == [
        "baseline",
        "edit",
    ]
    assert calls == 1
    assert source.read_text(encoding="utf-8").count("contradicts") == 1
    assert not store.path.exists()
