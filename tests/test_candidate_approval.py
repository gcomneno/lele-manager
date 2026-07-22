from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import ast
import json
from pathlib import Path

import pytest

from lele_manager.adapters.canonical_markdown_vault import (
    FilesystemCanonicalMarkdownVault,
)
from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.adapters.vault_jsonl_refresh import VaultJsonlRefresh
from lele_manager.application.candidate_approval import (
    ApprovalIdentityCollisionError,
    ApprovalPathCollisionError,
    ApprovalVaultStorageError,
    CandidateApprovalNotFoundError,
    CandidateApprovalService,
    CanonicalLessonSpec,
    CanonicalVaultStorageError,
    DerivedRefreshPortError,
    InvalidApprovalInputError,
    InvalidApprovalLifecycleError,
    InvalidApprovalMetadataError,
    PartialApprovalError,
    PartialRefreshError,
    RefreshOutcome,
    StaleApprovalRevisionError,
    VaultWriteOutcome,
    canonical_lesson_for,
)
from lele_manager.application.lesson_candidate import (
    CandidateNotFoundError,
    CandidateProvenance,
    CandidateReviewAction,
    CandidateReviewEvent,
    CandidateRevisionConflictError,
    CandidateState,
    LessonCandidate,
)
from lele_manager.application.raw_source import SourceKind, SourceSpan
from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter
from lele_manager.core.doctor import check_markdown_files
from lele_manager.core.vault import write_lesson_markdown


NOW = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)


def reviewed(
    text: str = "Useful lesson", *, fingerprint: str = "sha256:source"
) -> LessonCandidate:
    original = LessonCandidate(
        text,
        CandidateProvenance(
            SourceKind.MARKDOWN,
            "inbox/lesson.md",
            fingerprint,
            NOW,
            2,
            SourceSpan(10, 23),
            {"run": "r1"},
            ({"kind": "trim"},),
        ),
        {
            "topic": "architecture",
            "source": "book",
            "importance": 4,
            "tags": ["design", "boundaries"],
            "date": "2026-07-20",
            "title": "Ports & Adapters",
        },
    )
    accepted = CandidateReviewEvent(
        1,
        CandidateReviewAction.ACCEPTED,
        NOW,
        CandidateState.STAGED,
        CandidateState.IN_REVIEW,
    )
    return replace(
        original, state=CandidateState.IN_REVIEW, revision=1, review_history=(accepted,)
    )


class Repository:
    def __init__(self, item: LessonCandidate) -> None:
        self.item = item
        self.updates = 0
        self.fail_update = False

    def create(self, item: LessonCandidate) -> LessonCandidate:
        self.item = item
        return item

    def get(self, candidate_id: str) -> LessonCandidate:
        return self.item

    def list(self) -> tuple[LessonCandidate, ...]:
        return (self.item,)

    def update(
        self, candidate_id: str, item: LessonCandidate, *, expected_revision: int
    ) -> LessonCandidate:
        self.updates += 1
        if self.fail_update:
            raise CandidateRevisionConflictError("secret race")
        if self.item.revision != expected_revision:
            raise CandidateRevisionConflictError("race")
        self.item = item
        return item


class Clock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return NOW


class Refresh:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def refresh(self) -> RefreshOutcome:
        self.calls += 1
        if self.fail:
            raise DerivedRefreshPortError("secret output path")
        return RefreshOutcome()


def setup(tmp_path: Path, item: LessonCandidate | None = None):
    candidate = item or reviewed()
    repository, clock, refresh = Repository(candidate), Clock(), Refresh()
    vault = FilesystemCanonicalMarkdownVault(tmp_path / "vault")
    service = CandidateApprovalService(repository, vault, refresh, clock)
    return candidate, repository, vault, refresh, clock, service


def test_approval_writes_valid_markdown_and_complete_provenance(tmp_path: Path) -> None:
    item, repository, _, refresh, clock, service = setup(tmp_path)
    result = service.approve(item.candidate_id, expected_revision=1)

    path = tmp_path / "vault" / result.relative_vault_path
    assert result.vault_write_outcome is VaultWriteOutcome.CREATED
    assert result.candidate_state_changed is True
    assert repository.item.state is CandidateState.APPROVED
    assert repository.item.revision == 2
    assert repository.item.review_history[-1].action is CandidateReviewAction.APPROVED
    assert clock.calls == refresh.calls == 1
    assert result.lesson_id == result.relative_vault_path.removesuffix(".md")
    assert result.relative_vault_path.startswith(
        "architecture/2026-07-20.ports-adapters-"
    )
    frontmatter, body = parse_markdown_with_frontmatter(
        path.read_text(encoding="utf-8")
    )
    assert body.strip() == item.effective_text
    assert frontmatter["provenance"] == {
        "candidate_id": item.candidate_id,
        "chunk_index": 2,
        "ingested_at": NOW.isoformat(),
        "run_metadata": {"run": "r1"},
        "source_fingerprint": "sha256:source",
        "source_kind": "markdown",
        "source_logical_name": "inbox/lesson.md",
        "source_span": {"end": 23, "start": 10},
        "transformations": [{"kind": "trim"}],
    }
    assert check_markdown_files([path], vault_dir=tmp_path / "vault").valid


def test_deterministic_identity_and_title_collision_are_separate(
    tmp_path: Path,
) -> None:
    first, _, _, _, _, first_service = setup(
        tmp_path, reviewed("one", fingerprint="one")
    )
    first_result = first_service.approve(first.candidate_id, expected_revision=1)
    second, _, _, _, _, second_service = setup(
        tmp_path, reviewed("two", fingerprint="two")
    )
    second_result = second_service.approve(second.candidate_id, expected_revision=1)
    assert first_result.lesson_id != second_result.lesson_id
    assert first_result.relative_vault_path != second_result.relative_vault_path


@pytest.mark.parametrize("state", [CandidateState.STAGED, CandidateState.REJECTED])
def test_non_reviewed_states_rejected(tmp_path: Path, state: CandidateState) -> None:
    item = replace(reviewed(), state=state, revision=0, review_history=())
    item, repository, _, refresh, clock, service = setup(tmp_path, item)
    with pytest.raises(InvalidApprovalLifecycleError):
        service.approve(item.candidate_id, expected_revision=0)
    assert repository.updates == refresh.calls == clock.calls == 0
    assert not (tmp_path / "vault").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"importance": True},
        {"date": "2026-02-30"},
        {"tags": []},
        {"topic": "../bad"},
        {"unknown": "value"},
    ],
)
def test_invalid_metadata_changes_nothing(
    tmp_path: Path, change: dict[str, object]
) -> None:
    item = reviewed()
    metadata = dict(item.proposed_metadata or {})
    metadata.update(change)
    item = replace(item, proposed_metadata=metadata)
    item, repository, _, refresh, clock, service = setup(tmp_path, item)
    with pytest.raises(InvalidApprovalMetadataError):
        service.approve(item.candidate_id, expected_revision=1)
    assert repository.updates == refresh.calls == clock.calls == 0


def test_stale_precedes_vault_clock_and_refresh(tmp_path: Path) -> None:
    item, repository, _, refresh, clock, service = setup(tmp_path)
    with pytest.raises(StaleApprovalRevisionError):
        service.approve(item.candidate_id, expected_revision=0)
    assert repository.updates == refresh.calls == clock.calls == 0
    assert not (tmp_path / "vault").exists()


def test_collision_never_overwrites(tmp_path: Path) -> None:
    item, repository, _, refresh, clock, service = setup(tmp_path)
    from lele_manager.application.candidate_approval import canonical_lesson_for

    path = tmp_path / "vault" / canonical_lesson_for(item).relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"occupied")
    with pytest.raises(ApprovalPathCollisionError):
        service.approve(item.candidate_id, expected_revision=1)
    assert path.read_bytes() == b"occupied"
    assert repository.updates == refresh.calls == clock.calls == 0


def test_repository_failure_then_retry_recovers_without_rewrite(tmp_path: Path) -> None:
    item, repository, _, refresh, clock, service = setup(tmp_path)
    repository.fail_update = True
    with pytest.raises(PartialApprovalError) as caught:
        service.approve(item.candidate_id, expected_revision=1)
    path = tmp_path / "vault" / caught.value.relative_vault_path
    before = path.stat().st_mtime_ns
    repository.fail_update = False
    result = service.approve(item.candidate_id, expected_revision=1)
    assert result.vault_write_outcome is VaultWriteOutcome.IDENTICAL
    assert path.stat().st_mtime_ns == before
    assert clock.calls == 2
    assert refresh.calls == 1


def test_refresh_failure_and_approved_retry_are_idempotent(tmp_path: Path) -> None:
    item, repository, _, refresh, clock, service = setup(tmp_path)
    refresh.fail = True
    with pytest.raises(PartialRefreshError) as caught:
        service.approve(item.candidate_id, expected_revision=1)
    assert caught.value.partial_result.candidate_revision == 2
    refresh.fail = False
    result = service.approve(item.candidate_id, expected_revision=2)
    assert result.candidate_state_changed is False
    assert result.vault_write_outcome is VaultWriteOutcome.IDENTICAL
    assert repository.updates == 1
    assert clock.calls == 1
    assert refresh.calls == 2


def test_approved_missing_or_changed_file_is_controlled(tmp_path: Path) -> None:
    item, repository, _, refresh, clock, service = setup(tmp_path)
    result = service.approve(item.candidate_id, expected_revision=1)
    path = tmp_path / "vault" / result.relative_vault_path
    path.unlink()
    with pytest.raises(ApprovalPathCollisionError):
        service.approve(item.candidate_id, expected_revision=2)
    assert repository.updates == 1
    assert refresh.calls == 1
    assert clock.calls == 1


def test_nested_provenance_order_has_identical_specification_and_bytes(
    tmp_path: Path,
) -> None:
    left = reviewed()
    right = LessonCandidate(
        left.text,
        CandidateProvenance(
            left.provenance.source_kind,
            left.provenance.source_logical_name,
            left.provenance.source_fingerprint,
            left.provenance.ingested_at,
            left.provenance.chunk_index,
            left.provenance.source_span,
            {"outer": {"b": 2, "a": 1}, "items": [{"z": 0, "a": 9}]},
            ({"nested": {"y": 2, "x": 1}},),
        ),
        left.proposed_metadata,
    )
    left = replace(
        left,
        provenance=CandidateProvenance(
            left.provenance.source_kind,
            left.provenance.source_logical_name,
            left.provenance.source_fingerprint,
            left.provenance.ingested_at,
            left.provenance.chunk_index,
            left.provenance.source_span,
            {"items": [{"a": 9, "z": 0}], "outer": {"a": 1, "b": 2}},
            ({"nested": {"x": 1, "y": 2}},),
        ),
    )
    right = replace(right, state=left.state, revision=left.revision,
                    review_history=left.review_history)
    left_spec, right_spec = canonical_lesson_for(left), canonical_lesson_for(right)
    assert left_spec == right_spec
    left_before = left.provenance.run_metadata
    first = FilesystemCanonicalMarkdownVault(tmp_path / "one")
    second = FilesystemCanonicalMarkdownVault(tmp_path / "two")
    first.publish(left_spec)
    second.publish(right_spec)
    assert (tmp_path / "one" / left_spec.relative_path).read_bytes() == (
        tmp_path / "two" / right_spec.relative_path
    ).read_bytes()
    assert left.provenance.run_metadata is left_before


@pytest.mark.parametrize("field", ["run_metadata", "transformations"])
def test_cyclic_candidate_provenance_is_controlled_without_mutation(
    field: str,
) -> None:
    item = reviewed()
    if field == "run_metadata":
        cyclic: dict[str, object] = {}
        cyclic["self"] = cyclic
        hostile: object = cyclic
    else:
        sequence: list[object] = []
        sequence.append(sequence)
        hostile = sequence
    object.__setattr__(item.provenance, field, hostile)

    with pytest.raises(InvalidApprovalMetadataError, match="must not be cyclic"):
        canonical_lesson_for(item)

    assert getattr(item.provenance, field) is hostile
    if field == "run_metadata":
        assert cyclic["self"] is cyclic
    else:
        assert sequence[0] is sequence


def test_shared_non_cyclic_candidate_provenance_is_supported() -> None:
    item = reviewed()
    shared = {"value": [1, 2]}
    run_metadata = {"first": shared, "second": shared}
    object.__setattr__(item.provenance, "run_metadata", run_metadata)

    spec = canonical_lesson_for(item)

    assert spec.provenance["run_metadata"] == {
        "first": {"value": [1, 2]},
        "second": {"value": [1, 2]},
    }
    assert item.provenance.run_metadata is run_metadata
    assert run_metadata["first"] is run_metadata["second"] is shared


@pytest.mark.parametrize("bad", [{1: "bad"}, {"bad": object()}])
def test_unsupported_canonical_provenance_is_controlled(
    tmp_path: Path, bad: dict[object, object]
) -> None:
    spec = canonical_lesson_for(reviewed())
    hostile = replace(spec, provenance=bad)  # type: ignore[arg-type]
    with pytest.raises(CanonicalVaultStorageError):
        FilesystemCanonicalMarkdownVault(tmp_path / "vault").publish(hostile)


@pytest.mark.parametrize("container", [dict, list])
def test_cyclic_canonical_provenance_is_controlled(
    tmp_path: Path, container: type[dict[object, object]] | type[list[object]]
) -> None:
    cyclic: dict[object, object] | list[object] = container()
    if isinstance(cyclic, dict):
        cyclic["self"] = cyclic
    else:
        cyclic.append(cyclic)
    spec = canonical_lesson_for(reviewed())
    hostile = replace(spec, provenance={"cyclic": cyclic})

    with pytest.raises(CanonicalVaultStorageError, match="must not be cyclic"):
        FilesystemCanonicalMarkdownVault(tmp_path / "vault").publish(hostile)


def test_real_repository_approval_persists_complete_candidate(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    original = reviewed()
    repository = JsonCandidateRepository(path)
    repository.create(original)
    refresh, clock = Refresh(), Clock()
    service = CandidateApprovalService(
        repository, FilesystemCanonicalMarkdownVault(tmp_path / "vault"), refresh, clock
    )
    result = service.approve(original.candidate_id, expected_revision=1)
    loaded = JsonCandidateRepository(path).get(original.candidate_id)
    assert loaded.state is CandidateState.APPROVED
    assert loaded.revision == original.revision + 1 == result.candidate_revision
    assert loaded.review_history[:-1] == original.review_history
    event = loaded.review_history[-1]
    assert event.action is CandidateReviewAction.APPROVED
    assert event.previous_state is CandidateState.IN_REVIEW
    assert event.resulting_state is CandidateState.APPROVED
    assert event.occurred_at == NOW
    assert loaded.text == original.text
    assert loaded.provenance == original.provenance
    assert loaded.proposed_text == original.proposed_text
    assert loaded.proposed_metadata == original.proposed_metadata
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["candidates"][0]["review_history"][-1]["action"] == "approved"
    before = path.read_bytes()
    retry = CandidateApprovalService(
        JsonCandidateRepository(path),
        FilesystemCanonicalMarkdownVault(tmp_path / "vault"),
        refresh,
        clock,
    ).approve(original.candidate_id, expected_revision=2)
    assert retry.candidate_state_changed is False
    assert path.read_bytes() == before
    assert clock.calls == 1
    assert refresh.calls == 2


class HostileRepository(Repository):
    def update(self, candidate_id: str, item: LessonCandidate, *, expected_revision: int) -> LessonCandidate:
        declared = self.item
        super().update(candidate_id, item, expected_revision=expected_revision)
        return declared


def test_inconsistent_declared_persistence_result_is_partial_and_skips_refresh(
    tmp_path: Path,
) -> None:
    item = reviewed()
    repository, refresh = HostileRepository(item), Refresh()
    service = CandidateApprovalService(
        repository, FilesystemCanonicalMarkdownVault(tmp_path / "vault"), refresh, Clock()
    )
    with pytest.raises(PartialApprovalError):
        service.approve(item.candidate_id, expected_revision=1)
    assert refresh.calls == 0


@pytest.mark.parametrize("error", [OSError("disk"), UnicodeError("encoding")])
def test_refresh_operational_error_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(
        "lele_manager.adapters.vault_jsonl_refresh.import_vault_to_jsonl",
        lambda *_: (_ for _ in ()).throw(error),
    )
    with pytest.raises(DerivedRefreshPortError, match="configured refresh failed"):
        VaultJsonlRefresh(tmp_path / "vault", tmp_path / "out.jsonl").refresh()


@pytest.mark.parametrize("error", [RuntimeError("bug"), AssertionError("bug"), ValueError("bug"), SystemExit(2)])
def test_refresh_programming_errors_propagate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    monkeypatch.setattr(
        "lele_manager.adapters.vault_jsonl_refresh.import_vault_to_jsonl",
        lambda *_: (_ for _ in ()).throw(error),
    )
    with pytest.raises(type(error)):
        VaultJsonlRefresh(tmp_path / "vault", tmp_path / "out.jsonl").refresh()


def test_application_approval_has_no_forbidden_imports() -> None:
    path = Path("src/lele_manager/application/candidate_approval.py")
    imported = {
        alias.name
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
    }
    forbidden = ("fastapi", "pandas", "lele_manager.cli", "lele_manager.gui", "lele_manager.frontend", "lele_manager.ml")
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imported for prefix in forbidden)


def test_invalid_id_and_missing_candidate_are_typed(tmp_path: Path) -> None:
    item, repository, _, _, _, service = setup(tmp_path)
    with pytest.raises(InvalidApprovalInputError):
        service.approve("bad", expected_revision=1)
    repository.get = lambda _: (_ for _ in ()).throw(CandidateNotFoundError("secret"))  # type: ignore[method-assign]
    with pytest.raises(CandidateApprovalNotFoundError):
        service.approve(item.candidate_id, expected_revision=1)


def test_lesson_id_at_another_path_preserves_original_bytes(tmp_path: Path) -> None:
    item, repository, vault, refresh, clock, service = setup(tmp_path)
    spec = canonical_lesson_for(item)
    other = tmp_path / "vault" / "elsewhere.md"
    other.parent.mkdir(parents=True)
    write_lesson_markdown(
        tmp_path / "vault", lesson_id=spec.lesson_id, body="other", topic="x",
        source="x", importance=1, tags=["x"], date="2026-01-01",
        relative_path="elsewhere.md",
    )
    before = other.read_bytes()
    with pytest.raises(ApprovalIdentityCollisionError):
        service.approve(item.candidate_id, expected_revision=1)
    assert other.read_bytes() == before
    assert repository.updates == refresh.calls == clock.calls == 0


def test_destination_valid_different_id_preserves_original_bytes(tmp_path: Path) -> None:
    item, repository, _, refresh, clock, service = setup(tmp_path)
    spec = canonical_lesson_for(item)
    destination = write_lesson_markdown(
        tmp_path / "vault", lesson_id="different/id", body="occupied", topic="x",
        source="x", importance=1, tags=["x"], date="2026-01-01",
        relative_path=spec.relative_path,
    )
    before = destination.read_bytes()
    with pytest.raises(ApprovalPathCollisionError):
        service.approve(item.candidate_id, expected_revision=1)
    assert destination.read_bytes() == before
    assert repository.updates == refresh.calls == clock.calls == 0


class FailingVault:
    def publish(self, lesson: CanonicalLessonSpec) -> VaultWriteOutcome:
        raise CanonicalVaultStorageError("secret path")

    def verify(self, lesson: CanonicalLessonSpec) -> VaultWriteOutcome:
        raise AssertionError("not reached")


def test_declared_vault_failure_keeps_candidate_and_skips_refresh(tmp_path: Path) -> None:
    item, repository, refresh, clock = reviewed(), Repository(reviewed()), Refresh(), Clock()
    service = CandidateApprovalService(repository, FailingVault(), refresh, clock)
    with pytest.raises(ApprovalVaultStorageError, match="canonical vault operation failed"):
        service.approve(item.candidate_id, expected_revision=1)
    assert repository.item.state is CandidateState.IN_REVIEW
    assert repository.updates == refresh.calls == clock.calls == 0


class RealRaceRepository:
    def __init__(self, repository: JsonCandidateRepository) -> None:
        self.repository = repository

    def create(self, item: LessonCandidate) -> LessonCandidate:
        return self.repository.create(item)

    def get(self, candidate_id: str) -> LessonCandidate:
        return self.repository.get(candidate_id)

    def list(self) -> tuple[LessonCandidate, ...]:
        return self.repository.list()

    def update(self, candidate_id: str, item: LessonCandidate, *, expected_revision: int) -> LessonCandidate:
        self.repository.update(candidate_id, item, expected_revision=expected_revision)
        raise CandidateRevisionConflictError("lost response after competing update")


def test_exact_bytes_recover_after_real_repository_update_race(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidates.json"
    item = reviewed()
    real = JsonCandidateRepository(candidate_path)
    real.create(item)
    vault_path = tmp_path / "vault"
    service = CandidateApprovalService(
        RealRaceRepository(real), FilesystemCanonicalMarkdownVault(vault_path), Refresh(), Clock()
    )
    with pytest.raises(PartialApprovalError) as caught:
        service.approve(item.candidate_id, expected_revision=1)
    lesson_path = vault_path / caught.value.relative_vault_path
    before = lesson_path.read_bytes()
    recovered = CandidateApprovalService(
        JsonCandidateRepository(candidate_path), FilesystemCanonicalMarkdownVault(vault_path),
        Refresh(), Clock(),
    ).approve(item.candidate_id, expected_revision=2)
    assert recovered.candidate_state_changed is False
    assert recovered.vault_write_outcome is VaultWriteOutcome.IDENTICAL
    assert lesson_path.read_bytes() == before
