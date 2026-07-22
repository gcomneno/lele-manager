from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from lele_manager.api import tritalele
from lele_manager.api.server import app
from lele_manager.application.candidate_approval import (
    ApprovalResult,
    PartialApprovalError,
    PartialRefreshError,
    RefreshOutcome,
    VaultWriteOutcome,
    canonical_lesson_for,
)
from lele_manager.application.candidate_review import (
    CandidateReviewFilter,
    CandidateReviewStorageError,
)
from lele_manager.application.lesson_candidate import CandidateState
from lele_manager.application.raw_source import SourceKind
from lele_manager.application.raw_source_ingestion import PartialIngestionError
from lele_manager.core.paths import candidates_path
from lele_manager.core.vault import write_lesson_markdown


API = "/api/v1/tritalele"
EXPECTED_PATHS = {
    f"{API}/ingestion/preview": {"post"},
    f"{API}/ingestion/stage": {"post"},
    f"{API}/candidates": {"get"},
    f"{API}/candidates/{{candidate_id}}": {"get", "patch"},
    f"{API}/candidates/{{candidate_id}}/accept": {"post"},
    f"{API}/candidates/{{candidate_id}}/reject": {"post"},
    f"{API}/candidates/{{candidate_id}}/approve": {"post"},
}


@pytest.fixture(autouse=True)
def isolated_api_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    app.dependency_overrides.clear()
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_VAULT_DIR", str(tmp_path / "vault"))
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def raw_payload(
    content: str = "Alpha paragraph.\n\nBeta paragraph.",
    *,
    source_kind: str = "plain_text",
    logical_name: str = "notes.txt",
    max_characters: int = 18,
) -> dict[str, object]:
    return {
        "content": content,
        "source_kind": source_kind,
        "logical_name": logical_name,
        "max_characters": max_characters,
    }


def metadata(
    *, topic: str = "python", title: str = "Stable API"
) -> dict[str, object]:
    return {
        "topic": topic,
        "source": "api-test",
        "importance": 4,
        "tags": ["api", "review"],
        "date": "2026-07-22",
        "title": title,
    }


def stage_one(
    client: TestClient,
    *,
    content: str = "One complete candidate.",
    logical_name: str = "one.txt",
) -> dict[str, object]:
    response = client.post(
        f"{API}/ingestion/stage",
        json=raw_payload(
            content,
            logical_name=logical_name,
            max_characters=2_000,
        ),
    )
    assert response.status_code == 200, response.text
    return response.json()


def candidate_id(result: dict[str, object]) -> str:
    ids = result["candidate_ids"]
    assert isinstance(ids, list) and len(ids) == 1
    return str(ids[0])


def prepare_accepted_candidate(
    client: TestClient,
    *,
    logical_name: str = "approval.txt",
    topic: str = "python",
    title: str = "Approval",
) -> tuple[str, int]:
    created = stage_one(client, logical_name=logical_name)
    item_id = candidate_id(created)
    revised = client.patch(
        f"{API}/candidates/{item_id}",
        json={"expected_revision": 0, "proposed_metadata": metadata(topic=topic, title=title)},
    )
    assert revised.status_code == 200, revised.text
    accepted = client.post(
        f"{API}/candidates/{item_id}/accept",
        json={"expected_revision": 1, "reason": "ready"},
    )
    assert accepted.status_code == 200, accepted.text
    return item_id, int(accepted.json()["revision"])


def test_openapi_exposes_exact_versioned_surface_and_schemas() -> None:
    document = app.openapi()
    expected_operations = {
        (path, method)
        for path, methods in EXPECTED_PATHS.items()
        for method in methods
    }
    actual_operations = {
        (path, method)
        for path, path_item in document["paths"].items()
        if path.startswith(API)
        for method in path_item
        if method in {"get", "patch", "post", "put", "delete"}
    }

    assert actual_operations == expected_operations
    for existing_path in (
        "/health",
        "/lessons",
        "/integrations/v1/lessons",
        "/vault/status",
    ):
        assert existing_path in document["paths"]

    schemas = document["components"]["schemas"]
    for schema in (
        "RawSourceRequest",
        "CanonicalMetadataRequest",
        "CandidateRevisionRequest",
        "CandidateResponse",
        "CandidateListResponse",
        "IngestionResultResponse",
        "ApprovalResultResponse",
        "APIErrorResponse",
    ):
        assert schema in schemas

    operation_ids: list[str] = []
    for path, method in expected_operations:
        operation = document["paths"][path][method]
        operation_ids.append(operation["operationId"])
        assert operation["operationId"].startswith("tritalele_")
        assert operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"].startswith("#/components/schemas/")
        for status, response in operation["responses"].items():
            if status in {"200", "422"}:
                continue
            assert response["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/APIErrorResponse"
            }
        if method in {"patch", "post"}:
            assert operation["requestBody"]["content"]["application/json"][
                "schema"
            ]["$ref"].startswith("#/components/schemas/")
    assert len(operation_ids) == len(set(operation_ids))


def test_unknown_request_fields_are_rejected(client: TestClient) -> None:
    payload = raw_payload()
    payload["server_path"] = "/private/source.md"

    response = client.post(f"{API}/ingestion/preview", json=payload)

    assert response.status_code == 422
    assert "server_path" in response.text


@pytest.mark.parametrize(
    "payload",
    [
        raw_payload(logical_name=""),
        raw_payload(max_characters=0),
    ],
)
def test_domain_level_raw_source_inputs_return_structured_400(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post(f"{API}/ingestion/preview", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] in {
        "invalid_raw_source",
        "invalid_chunking_settings",
    }


@pytest.mark.parametrize(
    ("source_kind", "logical_name", "content"),
    [
        ("markdown", "lesson.md", "# One\n\nBody\n\n## Two\n\nMore"),
        ("plain_text", "notes.txt", "One paragraph.\n\nTwo paragraph."),
        ("stdin", "stdin", "Pasted from standard input.\n\nSecond block."),
    ],
)
def test_preview_is_deterministic_and_never_mutates_storage(
    client: TestClient,
    tmp_path: Path,
    source_kind: str,
    logical_name: str,
    content: str,
) -> None:
    candidate_file = tmp_path / "data" / "candidates.json"
    vault = tmp_path / "vault"
    projection = tmp_path / "data" / "lessons.jsonl"
    payload = raw_payload(
        content,
        source_kind=source_kind,
        logical_name=logical_name,
        max_characters=16,
    )

    first = client.post(f"{API}/ingestion/preview", json=payload)
    second = client.post(f"{API}/ingestion/preview", json=payload)

    assert first.status_code == second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["preview"] is True
    assert first_body["candidate_ids"] == second_body["candidate_ids"]
    assert first_body["candidate_ids"] == sorted(
        first_body["candidate_ids"],
        key=lambda item: next(
            candidate["provenance"]["chunk_index"]
            for candidate in first_body["candidates"]
            if candidate["candidate_id"] == item
        ),
    )
    assert first_body["created_candidate_ids"] == []
    assert first_body["pending_candidate_ids"] == first_body["candidate_ids"]
    assert not candidate_file.exists()
    assert not vault.exists()
    assert not projection.exists()


def test_preview_preserves_existing_artifacts_byte_for_byte(
    client: TestClient, tmp_path: Path
) -> None:
    existing = stage_one(client, content="Existing staged source.")
    assert existing["counts"]["created"] == 1  # type: ignore[index]
    candidate_file = tmp_path / "data" / "candidates.json"
    before_candidates = candidate_file.read_bytes()
    vault_file = tmp_path / "vault" / "keep.md"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text("keep-vault", encoding="utf-8")
    projection = tmp_path / "data" / "lessons.jsonl"
    projection.write_text("keep-projection\n", encoding="utf-8")

    response = client.post(
        f"{API}/ingestion/preview",
        json=raw_payload("A different source.", logical_name="different.txt"),
    )

    assert response.status_code == 200
    assert candidate_file.read_bytes() == before_candidates
    assert vault_file.read_text(encoding="utf-8") == "keep-vault"
    assert projection.read_text(encoding="utf-8") == "keep-projection\n"


def test_stage_creates_only_candidates_and_replay_is_idempotent(
    client: TestClient, tmp_path: Path
) -> None:
    payload = raw_payload(
        "First paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
        max_characters=19,
    )

    first = client.post(f"{API}/ingestion/stage", json=payload)
    second = client.post(f"{API}/ingestion/stage", json=payload)
    preview_existing = client.post(f"{API}/ingestion/preview", json=payload)

    assert first.status_code == second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["created_candidate_ids"] == first_body["candidate_ids"]
    assert first_body["skipped_candidate_ids"] == []
    assert second_body["candidate_ids"] == first_body["candidate_ids"]
    assert second_body["created_candidate_ids"] == []
    assert second_body["skipped_candidate_ids"] == first_body["candidate_ids"]
    assert preview_existing.status_code == 200
    assert preview_existing.json()["skipped_candidate_ids"] == first_body["candidate_ids"]
    assert preview_existing.json()["pending_candidate_ids"] == []
    assert (tmp_path / "data" / "candidates.json").is_file()
    assert not (tmp_path / "vault").exists()
    assert not (tmp_path / "data" / "lessons.jsonl").exists()


def test_missing_candidate_staging_lists_as_empty(client: TestClient) -> None:
    response = client.get(f"{API}/candidates")

    assert response.status_code == 200
    assert response.json() == {"count": 0, "candidates": []}


def test_candidate_filters_are_passed_to_review_service(client: TestClient) -> None:
    seen: list[CandidateReviewFilter] = []

    class RecordingReviewService:
        def list_candidates(
            self, filters: CandidateReviewFilter
        ) -> tuple[object, ...]:
            seen.append(filters)
            return ()

    app.dependency_overrides[tritalele.get_review_service] = RecordingReviewService

    response = client.get(
        f"{API}/candidates",
        params={
            "state": "staged",
            "source_kind": "markdown",
            "source_fingerprint": "sha256:source",
            "source_logical_name": "lesson.md",
            "chunk_index": 3,
        },
    )

    assert response.status_code == 200
    assert len(seen) == 1
    assert seen[0] == CandidateReviewFilter(
        state=CandidateState.STAGED,
        source_kind=SourceKind.MARKDOWN,
        source_fingerprint="sha256:source",
        source_logical_name="lesson.md",
        chunk_index=3,
    )


def test_candidate_list_filtering_and_order_are_deterministic(
    client: TestClient,
) -> None:
    first = stage_one(client, content="# Markdown candidate", logical_name="a.md")
    second = stage_one(client, content="Plain candidate", logical_name="b.txt")

    all_candidates = client.get(f"{API}/candidates")
    filtered = client.get(
        f"{API}/candidates", params={"source_logical_name": "a.md"}
    )

    assert all_candidates.status_code == filtered.status_code == 200
    ids = [item["candidate_id"] for item in all_candidates.json()["candidates"]]
    assert ids == sorted(ids)
    assert set(ids) == {candidate_id(first), candidate_id(second)}
    assert filtered.json()["count"] == 1
    assert filtered.json()["candidates"][0]["candidate_id"] == candidate_id(first)


def test_malformed_staging_is_a_sanitized_operational_error(
    client: TestClient, tmp_path: Path
) -> None:
    path = tmp_path / "data" / "candidates.json"
    path.parent.mkdir(parents=True)
    path.write_text("not-json /private/secret", encoding="utf-8")

    response = client.get(f"{API}/candidates")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "candidate_storage_unavailable"
    assert "/private/secret" not in response.text
    assert "MalformedStagingDataError" not in response.text


def test_candidate_retrieval_has_stable_transport_only_representation(
    client: TestClient, tmp_path: Path
) -> None:
    created = stage_one(client)
    item_id = candidate_id(created)

    response = client.get(f"{API}/candidates/{item_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "candidate_id",
        "state",
        "revision",
        "original_text",
        "proposed_text",
        "effective_text",
        "proposed_metadata",
        "provenance",
        "review_history",
    }
    assert body["candidate_id"] == item_id
    assert body["original_text"] == body["effective_text"]
    assert body["provenance"]["ingested_at"].endswith("+00:00")
    assert set(body["provenance"]) == {
        "source_kind",
        "source_logical_name",
        "source_fingerprint",
        "ingested_at",
        "chunk_index",
        "source_span",
        "run_metadata",
        "transformations",
    }
    assert str(tmp_path) not in response.text
    assert "JsonCandidateRepository" not in response.text
    assert "MappingProxyType" not in response.text


def test_missing_candidate_returns_structured_404(client: TestClient) -> None:
    response = client.get(f"{API}/candidates/sha256:{'0' * 64}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "candidate_not_found", "message": "Candidate was not found."}
    }


def test_revision_supports_text_metadata_and_complete_updates(
    client: TestClient,
) -> None:
    text_item = candidate_id(stage_one(client, logical_name="text.txt"))
    metadata_item = candidate_id(stage_one(client, logical_name="metadata.txt"))
    complete_item = candidate_id(stage_one(client, logical_name="complete.txt"))

    initial_metadata = client.patch(
        f"{API}/candidates/{text_item}",
        json={
            "expected_revision": 0,
            "proposed_metadata": metadata(title="Preserved metadata"),
        },
    )
    text_response = client.patch(
        f"{API}/candidates/{text_item}",
        json={"expected_revision": 1, "proposed_text": "Rewritten text."},
    )
    initial_text = client.patch(
        f"{API}/candidates/{metadata_item}",
        json={"expected_revision": 0, "proposed_text": "Preserved text."},
    )
    metadata_response = client.patch(
        f"{API}/candidates/{metadata_item}",
        json={"expected_revision": 1, "proposed_metadata": metadata(title="Metadata")},
    )
    complete_response = client.patch(
        f"{API}/candidates/{complete_item}",
        json={
            "expected_revision": 0,
            "proposed_text": "Complete rewrite.",
            "proposed_metadata": metadata(title="Complete"),
            "reason": "editorial pass",
        },
    )

    assert initial_metadata.status_code == initial_text.status_code == 200
    assert text_response.status_code == 200
    assert text_response.json()["proposed_text"] == "Rewritten text."
    assert text_response.json()["proposed_metadata"] == initial_metadata.json()[
        "proposed_metadata"
    ]
    assert metadata_response.status_code == 200
    assert metadata_response.json()["proposed_text"] == "Preserved text."
    assert metadata_response.json()["proposed_metadata"]["title"] == "Metadata"
    assert complete_response.status_code == 200
    assert complete_response.json()["effective_text"] == "Complete rewrite."
    assert complete_response.json()["review_history"][-1]["reason"] == "editorial pass"


def test_revision_rejects_incomplete_noop_and_identical_proposals(
    client: TestClient,
) -> None:
    item_id = candidate_id(stage_one(client))

    incomplete = client.patch(
        f"{API}/candidates/{item_id}",
        json={"expected_revision": 0, "proposed_metadata": {"topic": "python"}},
    )
    no_op = client.patch(
        f"{API}/candidates/{item_id}", json={"expected_revision": 0}
    )
    first = client.patch(
        f"{API}/candidates/{item_id}",
        json={"expected_revision": 0, "proposed_text": "Changed."},
    )
    identical = client.patch(
        f"{API}/candidates/{item_id}",
        json={"expected_revision": 1, "proposed_text": "Changed."},
    )

    assert incomplete.status_code == 422
    assert no_op.status_code == 422
    assert first.status_code == 200
    assert identical.status_code == 400
    assert identical.json()["detail"]["code"] == "invalid_candidate_review_input"
    current = client.get(f"{API}/candidates/{item_id}").json()
    assert current["revision"] == 1


def test_stale_revision_does_not_mutate_source_or_provenance(
    client: TestClient,
) -> None:
    item_id = candidate_id(stage_one(client))
    original = client.get(f"{API}/candidates/{item_id}").json()
    first = client.patch(
        f"{API}/candidates/{item_id}",
        json={"expected_revision": 0, "proposed_text": "First edit."},
    )
    stale = client.patch(
        f"{API}/candidates/{item_id}",
        json={"expected_revision": 0, "proposed_text": "Stale edit."},
    )
    current = client.get(f"{API}/candidates/{item_id}").json()

    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_candidate_revision"
    assert current["revision"] == 1
    assert current["proposed_text"] == "First edit."
    assert current["original_text"] == original["original_text"]
    assert current["provenance"] == original["provenance"]


def test_accept_and_reject_enforce_lifecycle_and_expected_revision(
    client: TestClient,
) -> None:
    accepted_id = candidate_id(stage_one(client, logical_name="accept.txt"))
    rejected_id = candidate_id(stage_one(client, logical_name="reject.txt"))

    accepted = client.post(
        f"{API}/candidates/{accepted_id}/accept",
        json={"expected_revision": 0, "reason": "good"},
    )
    repeated_accept = client.post(
        f"{API}/candidates/{accepted_id}/accept",
        json={"expected_revision": 1},
    )
    rejected = client.post(
        f"{API}/candidates/{rejected_id}/reject",
        json={"expected_revision": 0},
    )
    repeated_reject = client.post(
        f"{API}/candidates/{rejected_id}/reject",
        json={"expected_revision": 1},
    )
    stale = client.post(
        f"{API}/candidates/{accepted_id}/reject",
        json={"expected_revision": 0},
    )

    assert accepted.status_code == rejected.status_code == 200
    assert accepted.json()["state"] == "in_review"
    assert rejected.json()["state"] == "rejected"
    assert repeated_accept.status_code == repeated_reject.status_code == 409
    assert repeated_accept.json()["detail"]["code"] == "invalid_candidate_transition"
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_candidate_revision"


def test_approval_is_ordered_and_idempotent(client: TestClient, tmp_path: Path) -> None:
    item_id, revision = prepare_accepted_candidate(client)
    projection = tmp_path / "data" / "lessons.jsonl"
    vault = tmp_path / "vault"
    assert not projection.exists()

    approved = client.post(
        f"{API}/candidates/{item_id}/approve",
        json={"expected_revision": revision},
    )

    assert approved.status_code == 200, approved.text
    result = approved.json()
    artifact = vault / result["relative_vault_path"]
    assert artifact.is_file()
    assert result["vault_write_outcome"] == "created"
    assert result["candidate_state_changed"] is True
    assert result["refresh_outcome"] == {"refreshed": True}
    assert projection.is_file()
    records = [json.loads(line) for line in projection.read_text(encoding="utf-8").splitlines()]
    assert [record["id"] for record in records] == [result["lesson_id"]]
    assert client.get(f"{API}/candidates/{item_id}").json()["state"] == "approved"
    assert len(list(vault.rglob("*.md"))) == 1

    repeated = client.post(
        f"{API}/candidates/{item_id}/approve",
        json={"expected_revision": result["candidate_revision"]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["vault_write_outcome"] == "identical"
    assert repeated.json()["candidate_state_changed"] is False
    assert len(list(vault.rglob("*.md"))) == 1


def test_approval_does_not_auto_accept_and_validates_metadata_and_revision(
    client: TestClient,
) -> None:
    staged_id = candidate_id(stage_one(client, logical_name="staged.txt"))
    revised = client.patch(
        f"{API}/candidates/{staged_id}",
        json={"expected_revision": 0, "proposed_metadata": metadata()},
    )
    staged_approval = client.post(
        f"{API}/candidates/{staged_id}/approve",
        json={"expected_revision": 1},
    )

    missing_metadata_id = candidate_id(
        stage_one(client, logical_name="missing-metadata.txt")
    )
    accepted = client.post(
        f"{API}/candidates/{missing_metadata_id}/accept",
        json={"expected_revision": 0},
    )
    missing_metadata = client.post(
        f"{API}/candidates/{missing_metadata_id}/approve",
        json={"expected_revision": 1},
    )
    stale = client.post(
        f"{API}/candidates/{missing_metadata_id}/approve",
        json={"expected_revision": 0},
    )

    assert revised.status_code == accepted.status_code == 200
    assert staged_approval.status_code == 409
    assert staged_approval.json()["detail"]["code"] == "invalid_approval_lifecycle"
    assert client.get(f"{API}/candidates/{staged_id}").json()["state"] == "staged"
    assert missing_metadata.status_code == 400
    assert missing_metadata.json()["detail"]["code"] == "invalid_approval_metadata"
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_approval_revision"


def test_approval_path_and_identity_collisions_are_controlled(
    client: TestClient, tmp_path: Path
) -> None:
    path_id, path_revision = prepare_accepted_candidate(
        client, logical_name="path.txt", title="Path collision"
    )
    repository = tritalele.get_candidate_repository()
    path_lesson = canonical_lesson_for(repository.get(path_id))
    destination = tmp_path / "vault" / path_lesson.relative_path
    destination.parent.mkdir(parents=True)
    destination.write_text("occupied", encoding="utf-8")

    path_response = client.post(
        f"{API}/candidates/{path_id}/approve",
        json={"expected_revision": path_revision},
    )

    identity_id, identity_revision = prepare_accepted_candidate(
        client, logical_name="identity.txt", title="Identity collision"
    )
    identity_lesson = canonical_lesson_for(repository.get(identity_id))
    write_lesson_markdown(
        tmp_path / "vault",
        lesson_id=identity_lesson.lesson_id,
        body=identity_lesson.body,
        topic=identity_lesson.topic,
        source=identity_lesson.source,
        importance=identity_lesson.importance,
        tags=list(identity_lesson.tags),
        date=identity_lesson.date,
        title=identity_lesson.title,
        provenance=dict(identity_lesson.provenance),
        relative_path="elsewhere/identity.md",
    )
    identity_response = client.post(
        f"{API}/candidates/{identity_id}/approve",
        json={"expected_revision": identity_revision},
    )

    assert path_response.status_code == 409
    assert path_response.json()["detail"]["code"] == "approval_path_collision"
    assert identity_response.status_code == 409
    assert identity_response.json()["detail"]["code"] == "approval_identity_collision"


def test_partial_ingestion_exposes_stable_recovery_payload(client: TestClient) -> None:
    class FailingIngestionService:
        def ingest(self, source: object, settings: object, preview: bool = False) -> None:
            raise PartialIngestionError(
                created_candidate_ids=("created-a",),
                failed_candidate_id="failed-b",
                remaining_candidate_ids=("remaining-c",),
            )

    app.dependency_overrides[tritalele.get_ingestion_service] = FailingIngestionService

    response = client.post(f"{API}/ingestion/stage", json=raw_payload())

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "partial_ingestion",
            "message": "Candidate staging stopped after a partial ingestion.",
            "recovery": {
                "created_candidate_ids": ["created-a"],
                "failed_candidate_id": "failed-b",
                "remaining_candidate_ids": ["remaining-c"],
            },
        }
    }


@pytest.mark.parametrize("kind", ["approval", "refresh"])
def test_partial_approval_failures_expose_sanitized_recovery(
    client: TestClient, kind: str
) -> None:
    partial_result = ApprovalResult(
        candidate_id=f"sha256:{'1' * 64}",
        candidate_revision=3,
        lesson_id="python/lesson",
        relative_vault_path="python/lesson.md",
        vault_write_outcome=VaultWriteOutcome.CREATED,
        candidate_state_changed=True,
        refresh_outcome=RefreshOutcome(refreshed=False),
    )
    error = (
        PartialApprovalError(
            partial_result.candidate_id,
            partial_result.lesson_id,
            partial_result.relative_vault_path,
            partial_result.vault_write_outcome,
        )
        if kind == "approval"
        else PartialRefreshError(partial_result)
    )

    class FailingApprovalService:
        def approve(self, candidate_id: str, *, expected_revision: int) -> None:
            raise error

    app.dependency_overrides[tritalele.get_approval_service] = FailingApprovalService

    response = client.post(
        f"{API}/candidates/{partial_result.candidate_id}/approve",
        json={"expected_revision": 2},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == f"partial_{kind}"
    assert "/tmp/" not in response.text
    assert "Partial" not in response.text
    if kind == "approval":
        assert detail["recovery"] == {
            "candidate_id": partial_result.candidate_id,
            "lesson_id": partial_result.lesson_id,
            "relative_vault_path": partial_result.relative_vault_path,
            "vault_write_outcome": "created",
            "candidate_persistence_state": "unknown",
        }
        assert "retry" not in response.text.lower()
    else:
        assert detail["recovery"] == {
            "partial_approval_result": {
                "candidate_id": partial_result.candidate_id,
                "candidate_revision": partial_result.candidate_revision,
                "lesson_id": partial_result.lesson_id,
                "relative_vault_path": partial_result.relative_vault_path,
                "vault_write_outcome": "created",
                "candidate_state_changed": True,
                "refresh_outcome": {"refreshed": False},
            },
            "canonical_lesson_persisted": True,
            "candidate_approval_persisted": True,
            "projection_refreshed": False,
        }


def test_storage_failure_never_leaks_paths_or_exception_details(
    client: TestClient,
) -> None:
    class FailingReviewService:
        def list_candidates(self, filters: CandidateReviewFilter) -> None:
            raise CandidateReviewStorageError(
                "JsonCandidateRepository failed at /private/candidates.json: secret"
            )

    app.dependency_overrides[tritalele.get_review_service] = FailingReviewService

    response = client.get(f"{API}/candidates")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "candidate_storage_unavailable"
    assert "/private/candidates.json" not in response.text
    assert "secret" not in response.text
    assert "CandidateReviewStorageError" not in response.text


def test_full_api_happy_path(client: TestClient, tmp_path: Path) -> None:
    payload = raw_payload(
        "# API boundary\n\nA complete lesson candidate.",
        source_kind="markdown",
        logical_name="api-boundary.md",
        max_characters=2_000,
    )
    preview = client.post(f"{API}/ingestion/preview", json=payload)
    stage = client.post(f"{API}/ingestion/stage", json=payload)
    assert preview.status_code == stage.status_code == 200
    assert preview.json()["candidate_ids"] == stage.json()["candidate_ids"]
    item_id = candidate_id(stage.json())

    listed = client.get(f"{API}/candidates")
    fetched = client.get(f"{API}/candidates/{item_id}")
    revised = client.patch(
        f"{API}/candidates/{item_id}",
        json={
            "expected_revision": 0,
            "proposed_text": "Use a stable, versioned API boundary.",
            "proposed_metadata": metadata(title="Versioned boundary"),
        },
    )
    accepted = client.post(
        f"{API}/candidates/{item_id}/accept", json={"expected_revision": 1}
    )
    approved = client.post(
        f"{API}/candidates/{item_id}/approve", json={"expected_revision": 2}
    )

    assert listed.status_code == fetched.status_code == 200
    assert listed.json()["count"] == 1
    assert revised.status_code == accepted.status_code == approved.status_code == 200
    approval = approved.json()
    markdown = tmp_path / "vault" / approval["relative_vault_path"]
    assert markdown.is_file()
    markdown_text = markdown.read_text(encoding="utf-8")
    assert f"id: {approval['lesson_id']}" in markdown_text
    assert "Use a stable, versioned API boundary." in markdown_text
    final_candidate = client.get(f"{API}/candidates/{item_id}").json()
    assert final_candidate["state"] == "approved"
    projection = tmp_path / "data" / "lessons.jsonl"
    assert projection.is_file()
    assert approval["lesson_id"] in projection.read_text(encoding="utf-8")


def test_existing_api_paths_remain_compatible(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lele_manager.api import server

    data_path = tmp_path / "legacy-lessons.jsonl"
    monkeypatch.setattr(server, "DATA_PATH", data_path)

    health = client.get("/health")
    lessons = client.get("/lessons")
    integration = client.get("/integrations/v1/lessons")

    assert health.status_code == lessons.status_code == integration.status_code == 200
    assert health.json()["status"] == "ok"
    assert lessons.json() == []
    assert integration.json()["lessons"] == []
    openapi_paths = app.openapi()["paths"]
    for path in ("/health", "/lessons", "/integrations/v1/lessons", "/vault/status"):
        assert path in openapi_paths


def test_boundary_isolation_and_no_forbidden_framework_leakage() -> None:
    root = Path(__file__).parents[1]
    api_source = (root / "src/lele_manager/api/tritalele.py").read_text(
        encoding="utf-8"
    )
    server_source = (root / "src/lele_manager/api/server.py").read_text(
        encoding="utf-8"
    )

    assert "cli.tritalele" not in api_source
    assert "api.server" not in api_source
    assert "RawSourceIngestionService" in api_source
    assert "DeterministicRawSourceChunker" in api_source
    assert "hashlib" not in api_source
    assert "include_router(tritalele_router)" in server_source

    for directory in ("application", "core"):
        for module in (root / f"src/lele_manager/{directory}").glob("*.py"):
            source = module.read_text(encoding="utf-8")
            assert "from fastapi" not in source
            assert "import fastapi" not in source
            assert "from pydantic" not in source
            assert "import pydantic" not in source


def test_dependency_overrides_are_cleared_after_each_test() -> None:
    assert app.dependency_overrides == {}
    assert candidates_path().name == "candidates.json"
