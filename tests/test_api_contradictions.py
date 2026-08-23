from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.application.contradiction_resolution import (
    AuxiliaryResolutionResult,
    CanonicalResolutionResult,
    ContradictionResolutionConflictError,
    ContradictionResolutionNotFoundError,
    ContradictionResolutionRecoveryError,
    ContradictionResolutionStaleError,
)
from lele_manager.core.contradiction_review import PairIdentity


client = TestClient(server.app)


class RecordingService:
    def __init__(
        self,
        *,
        auxiliary_result: object | None = None,
        canonical_result: object | None = None,
        auxiliary_error: Exception | None = None,
        canonical_error: Exception | None = None,
    ) -> None:
        self.auxiliary_result = auxiliary_result
        self.canonical_result = canonical_result
        self.auxiliary_error = auxiliary_error
        self.canonical_error = canonical_error
        self.auxiliary_intents: list[object] = []
        self.canonical_intents: list[object] = []

    def resolve_auxiliary(self, intent: object) -> object:
        self.auxiliary_intents.append(intent)
        if self.auxiliary_error is not None:
            raise self.auxiliary_error
        assert self.auxiliary_result is not None
        return self.auxiliary_result

    def resolve_canonical(self, intent: object) -> object:
        self.canonical_intents.append(intent)
        if self.canonical_error is not None:
            raise self.canonical_error
        assert self.canonical_result is not None
        return self.canonical_result


def _patch_service(monkeypatch: pytest.MonkeyPatch, service: RecordingService) -> None:
    monkeypatch.setattr(
        server,
        "ContradictionResolutionService",
        lambda **_kwargs: service,
    )


def test_dismiss_maps_request_to_auxiliary_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RecordingService(
        auxiliary_result=AuxiliaryResolutionResult(
            vault_id="vault-1",
            pair=PairIdentity.from_ids("alpha/left", "alpha/right"),
            decision="dismissed",
            canonical_success=False,
            canonical_changed=False,
            derived_refresh_success=None,
        )
    )
    _patch_service(monkeypatch, service)

    response = client.post(
        "/contradictions/dismiss",
        json={
            "decision": "dismissed",
            "left_id": "alpha/left",
            "right_id": "alpha/right",
            "left_fingerprint": "left-fingerprint",
            "right_fingerprint": "right-fingerprint",
            "note": "Reviewed by human.",
        },
    )

    assert response.status_code == 200, response.text
    assert len(service.auxiliary_intents) == 1
    intent = service.auxiliary_intents[0]
    assert intent.decision == "dismissed"
    assert intent.left_id == "alpha/left"
    assert intent.right_id == "alpha/right"
    assert intent.left_fingerprint == "left-fingerprint"
    assert intent.right_fingerprint == "right-fingerprint"
    assert intent.note == "Reviewed by human."
    assert response.json() == {
        "vault_id": "vault-1",
        "left_id": "alpha/left",
        "right_id": "alpha/right",
        "decision": "dismissed",
        "canonical_success": False,
        "canonical_changed": False,
        "derived_refresh_success": None,
    }


@pytest.mark.parametrize(
    ("payload", "decision", "mutated_id", "referenced_id"),
    [
        (
            {
                "decision": "superseded-by",
                "superseded_id": "alpha/old",
                "replacement_id": "alpha/new",
                "expected_superseded_revision": "sha256:" + "a" * 64,
            },
            "superseded-by",
            "alpha/old",
            "alpha/new",
        ),
        (
            {
                "decision": "corrects",
                "correcting_id": "alpha/new",
                "corrected_id": "alpha/old",
                "expected_correcting_revision": "sha256:" + "b" * 64,
            },
            "corrects",
            "alpha/new",
            "alpha/old",
        ),
        (
            {
                "decision": "contradicts",
                "source_id": "alpha/a",
                "target_id": "alpha/b",
                "expected_source_revision": "sha256:" + "c" * 64,
            },
            "contradicts",
            "alpha/a",
            "alpha/b",
        ),
    ],
)
def test_resolve_maps_each_canonical_decision_to_service_intent(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, str],
    decision: str,
    mutated_id: str,
    referenced_id: str,
) -> None:
    service = RecordingService(
        canonical_result=CanonicalResolutionResult(
            vault_id="vault-1",
            decision=decision,  # type: ignore[arg-type]
            mutated_lesson_id=mutated_id,
            referenced_lesson_id=referenced_id,
            canonical_success=True,
            canonical_changed=True,
            derived_refresh_success=True,
            partial_success=False,
            canonical_revision="sha256:" + "d" * 64,
            revision=2,
        )
    )
    _patch_service(monkeypatch, service)

    response = client.post("/contradictions/resolve", json=payload)

    assert response.status_code == 200, response.text
    assert len(service.canonical_intents) == 1
    result = response.json()
    assert result["decision"] == decision
    assert result["mutated_lesson_id"] == mutated_id
    assert result["referenced_lesson_id"] == referenced_id
    assert result["canonical_success"] is True
    assert result["canonical_changed"] is True
    assert result["derived_refresh_success"] is True
    assert result["partial_success"] is False
    assert result["canonical_revision"] == "sha256:" + "d" * 64
    assert result["revision"] == 2


def test_resolve_returns_partial_success_as_successful_http_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RecordingService(
        canonical_result=CanonicalResolutionResult(
            vault_id="vault-1",
            decision="contradicts",
            mutated_lesson_id="alpha/a",
            referenced_lesson_id="alpha/b",
            canonical_success=True,
            canonical_changed=True,
            derived_refresh_success=False,
            partial_success=True,
            canonical_revision="sha256:" + "e" * 64,
            revision=3,
            refresh_error="refresh failed",
        )
    )
    _patch_service(monkeypatch, service)

    response = client.post(
        "/contradictions/resolve",
        json={
            "decision": "contradicts",
            "source_id": "alpha/a",
            "target_id": "alpha/b",
            "expected_source_revision": "sha256:" + "a" * 64,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["partial_success"] is True
    assert response.json()["derived_refresh_success"] is False
    assert response.json()["refresh_error"] == "refresh failed"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (
            ContradictionResolutionNotFoundError("missing"),
            404,
            "contradiction_not_found",
        ),
        (
            ContradictionResolutionStaleError("stale"),
            409,
            "contradiction_stale",
        ),
        (
            ContradictionResolutionConflictError("conflict"),
            409,
            "contradiction_conflict",
        ),
        (
            ContradictionResolutionRecoveryError("do not blindly retry"),
            503,
            "contradiction_recovery_indeterminate",
        ),
    ],
)
def test_resolve_maps_controlled_service_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status: int,
    code: str,
) -> None:
    service = RecordingService(canonical_error=error)
    _patch_service(monkeypatch, service)

    response = client.post(
        "/contradictions/resolve",
        json={
            "decision": "contradicts",
            "source_id": "alpha/a",
            "target_id": "alpha/b",
            "expected_source_revision": "sha256:" + "a" * 64,
        },
    )

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_recovery_error_explicitly_forbids_blind_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RecordingService(
        canonical_error=ContradictionResolutionRecoveryError(
            "canonical state is indeterminate; do not blindly retry"
        )
    )
    _patch_service(monkeypatch, service)

    response = client.post(
        "/contradictions/resolve",
        json={
            "decision": "contradicts",
            "source_id": "alpha/a",
            "target_id": "alpha/b",
            "expected_source_revision": "sha256:" + "a" * 64,
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "contradiction_recovery_indeterminate"
    assert detail["recovery"]["retry_safe"] is False


def test_resolve_rejects_unknown_decision_before_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RecordingService()
    _patch_service(monkeypatch, service)

    response = client.post(
        "/contradictions/resolve",
        json={
            "decision": "invented-truth",
            "source_id": "alpha/a",
            "target_id": "alpha/b",
            "expected_source_revision": "sha256:" + "a" * 64,
        },
    )

    assert response.status_code == 422
    assert service.canonical_intents == []


def test_dismiss_rejects_canonical_decision_before_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RecordingService()
    _patch_service(monkeypatch, service)

    response = client.post(
        "/contradictions/dismiss",
        json={
            "decision": "contradicts",
            "left_id": "alpha/a",
            "right_id": "alpha/b",
            "left_fingerprint": "left",
            "right_fingerprint": "right",
        },
    )

    assert response.status_code == 422
    assert service.auxiliary_intents == []


def _get_context(tmp_path, *, vault_id: str = "33333333-3333-4333-8333-333333333333"):
    from lele_manager.core.vault_registry import ActiveVaultContext

    return ActiveVaultContext(
        vault_id=vault_id,
        display_name="Contradiction API Test Vault",
        vault_dir=tmp_path / "vault",
        projection_path=tmp_path / "data" / "vaults" / vault_id / "lessons.jsonl",
        candidates_path=tmp_path / "data" / "vaults" / vault_id / "candidates.json",
        topic_model_path=tmp_path / "cache" / "vaults" / vault_id / "topic_model.joblib",
        duplicate_decision_scope=vault_id,
    )


def _get_write(context, lesson_id: str, *, body: str):
    from lele_manager.core.vault import write_lesson_markdown

    topic = lesson_id.split("/", 1)[0]
    return write_lesson_markdown(
        context.vault_dir,
        lesson_id=lesson_id,
        body=body,
        topic=topic,
        source="note",
        importance=3,
        tags=[topic],
        date="2026-08-22",
        title=lesson_id.rsplit("/", 1)[-1].title(),
        lifecycle="active",
    )


def _get_projection_row(context, lesson_id: str) -> dict[str, object]:
    from lele_manager.application.lesson_writing import read_canonical_lesson_snapshot

    snapshot = read_canonical_lesson_snapshot(
        vault_dir=context.vault_dir,
        lesson_id=lesson_id,
    )
    return {
        "id": snapshot.lesson_id,
        "text": snapshot.text,
        "title": snapshot.title,
        "topic": snapshot.topic,
        "source": snapshot.source,
        "importance": snapshot.importance,
        "tags": snapshot.tags,
        "date": snapshot.date,
        "lifecycle": snapshot.lifecycle,
        "superseded_by": snapshot.superseded_by,
        "relationships": snapshot.relationships,
    }


def test_get_contradictions_returns_explainable_actionable_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import pandas as pd

    context = _get_context(tmp_path)
    _get_write(
        context,
        "alpha/old",
        body="The cache must be enabled for this deployment.",
    )
    _get_write(
        context,
        "alpha/new",
        body="The cache must not be enabled for this deployment.",
    )

    rows = [
        _get_projection_row(context, "alpha/old"),
        _get_projection_row(context, "alpha/new"),
    ]

    monkeypatch.setattr(server, "get_active_vault_context", lambda: context)
    monkeypatch.setattr(
        server,
        "load_lessons_df",
        lambda supplied_context=None: pd.DataFrame(rows),
    )

    response = client.get("/contradictions", params={"limit": 20})

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["vault_id"] == context.vault_id
    assert payload["returned_candidates"] == 1
    assert payload["suppressed_candidates"] == 0
    assert len(payload["candidates"]) == 1

    candidate = payload["candidates"][0]

    assert [candidate["left_id"], candidate["right_id"]] == [
        "alpha/new",
        "alpha/old",
    ]
    assert "same-topic" in candidate["same_subject_reasons"]
    assert candidate["tension_reasons"]
    assert set(candidate["reasons"]) == (
        set(candidate["same_subject_reasons"])
        | set(candidate["tension_reasons"])
    )

    # The API exposes review/action tokens, not a factual truth judgment.
    assert candidate["left_fingerprint"]
    assert candidate["right_fingerprint"]
    assert candidate["left_canonical_revision"].startswith("sha256:")
    assert candidate["right_canonical_revision"].startswith("sha256:")
    assert candidate["resolution_available"] is True
    assert candidate["resolution_problem"] is None

    assert candidate["left_lesson"]["id"] == "alpha/new"
    assert candidate["right_lesson"]["id"] == "alpha/old"
    assert candidate["left_lesson"]["text"]
    assert candidate["right_lesson"]["text"]

    # Similarity is retrieval metadata only and is optional.
    assert candidate["similarity_score"] is None

    serialized = response.text.casefold()
    assert "verified contradiction" not in serialized
    assert "proven contradiction" not in serialized
    assert "true" not in candidate
    assert "false" not in candidate


def test_get_contradictions_applies_limit_after_auxiliary_suppression(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import pandas as pd

    from lele_manager.core.contradiction_review import material_fingerprint
    from lele_manager.core.contradiction_review_store import (
        CONTRADICTION_REVIEW_STORE_FILENAME,
        ContradictionReviewStore,
    )

    context = _get_context(tmp_path)

    _get_write(
        context,
        "alpha/old",
        body="Alpha caching must be enabled.",
    )
    _get_write(
        context,
        "alpha/new",
        body="Alpha caching must not be enabled.",
    )
    _get_write(
        context,
        "beta/old",
        body="Beta synchronization must be enabled.",
    )
    _get_write(
        context,
        "beta/new",
        body="Beta synchronization must not be enabled.",
    )

    rows = [
        _get_projection_row(context, lesson_id)
        for lesson_id in (
            "alpha/old",
            "alpha/new",
            "beta/old",
            "beta/new",
        )
    ]

    by_id = {str(row["id"]): row for row in rows}
    store = ContradictionReviewStore(
        context.candidates_path.parent / CONTRADICTION_REVIEW_STORE_FILENAME
    )
    store.save_decision(
        scope=context.vault_id,
        left_id="alpha/new",
        left_fingerprint=material_fingerprint(by_id["alpha/new"]),
        right_id="alpha/old",
        right_fingerprint=material_fingerprint(by_id["alpha/old"]),
        decision="dismissed",
    )

    monkeypatch.setattr(server, "get_active_vault_context", lambda: context)
    monkeypatch.setattr(
        server,
        "load_lessons_df",
        lambda supplied_context=None: pd.DataFrame(rows),
    )

    response = client.get("/contradictions", params={"limit": 1})

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["returned_candidates"] == 1
    assert payload["suppressed_candidates"] == 1

    pair = {
        payload["candidates"][0]["left_id"],
        payload["candidates"][0]["right_id"],
    }
    assert pair == {"beta/new", "beta/old"}


def test_get_contradictions_malformed_auxiliary_store_fails_visibly_without_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import pandas as pd

    from lele_manager.core.contradiction_review_store import (
        CONTRADICTION_REVIEW_STORE_FILENAME,
    )

    context = _get_context(tmp_path)
    _get_write(
        context,
        "alpha/old",
        body="The cache must be enabled.",
    )
    _get_write(
        context,
        "alpha/new",
        body="The cache must not be enabled.",
    )

    rows = [
        _get_projection_row(context, "alpha/old"),
        _get_projection_row(context, "alpha/new"),
    ]

    store_path = (
        context.candidates_path.parent
        / CONTRADICTION_REVIEW_STORE_FILENAME
    )
    store_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt = b"{not-json"
    store_path.write_bytes(corrupt)

    monkeypatch.setattr(server, "get_active_vault_context", lambda: context)
    monkeypatch.setattr(
        server,
        "load_lessons_df",
        lambda supplied_context=None: pd.DataFrame(rows),
    )

    response = client.get("/contradictions", params={"limit": 20})

    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "contradiction_store_failed"
    assert store_path.read_bytes() == corrupt


@pytest.mark.parametrize(
    "payload",
    [
        {
            "decision": "superseded-by",
            "superseded_id": "alpha/old",
            "replacement_id": "alpha/new",
            "expected_superseded_revision": "not-a-revision",
        },
        {
            "decision": "corrects",
            "correcting_id": "alpha/new",
            "corrected_id": "alpha/old",
            "expected_correcting_revision": "sha256:any",
        },
        {
            "decision": "contradicts",
            "source_id": "alpha/a",
            "target_id": "alpha/b",
            "expected_source_revision": "sha256:" + "A" * 64,
        },
    ],
)
def test_resolve_rejects_malformed_revision_tokens_before_service(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, str],
) -> None:
    service = RecordingService()
    _patch_service(monkeypatch, service)

    response = client.post("/contradictions/resolve", json=payload)

    assert response.status_code == 422
    assert service.canonical_intents == []


def test_get_contradictions_changed_material_invalidates_auxiliary_suppression(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import pandas as pd

    from lele_manager.core.contradiction_review import material_fingerprint
    from lele_manager.core.contradiction_review_store import (
        CONTRADICTION_REVIEW_STORE_FILENAME,
        ContradictionReviewStore,
    )

    context = _get_context(tmp_path)
    old_path = _get_write(
        context,
        "alpha/old",
        body="The cache must be enabled.",
    )
    _get_write(
        context,
        "alpha/new",
        body="The cache must not be enabled.",
    )

    initial_rows = [
        _get_projection_row(context, "alpha/old"),
        _get_projection_row(context, "alpha/new"),
    ]
    by_id = {str(row["id"]): row for row in initial_rows}

    store = ContradictionReviewStore(
        context.candidates_path.parent / CONTRADICTION_REVIEW_STORE_FILENAME
    )
    store.save_decision(
        scope=context.vault_id,
        left_id="alpha/new",
        left_fingerprint=material_fingerprint(by_id["alpha/new"]),
        right_id="alpha/old",
        right_fingerprint=material_fingerprint(by_id["alpha/old"]),
        decision="different-context",
    )

    # Change material canonical content while preserving the surfacing shape.
    old_text = old_path.read_text(encoding="utf-8")
    old_path.write_text(
        old_text.replace(
            "The cache must be enabled.",
            "The cache must always be enabled.",
        ),
        encoding="utf-8",
    )

    current_rows = [
        _get_projection_row(context, "alpha/old"),
        _get_projection_row(context, "alpha/new"),
    ]

    monkeypatch.setattr(server, "get_active_vault_context", lambda: context)
    monkeypatch.setattr(
        server,
        "load_lessons_df",
        lambda supplied_context=None: pd.DataFrame(current_rows),
    )

    response = client.get("/contradictions", params={"limit": 20})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["suppressed_candidates"] == 0
    assert payload["returned_candidates"] == 1
    assert {
        payload["candidates"][0]["left_id"],
        payload["candidates"][0]["right_id"],
    } == {"alpha/new", "alpha/old"}
