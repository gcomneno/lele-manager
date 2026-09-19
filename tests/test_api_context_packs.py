from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.core.context_pack_store import (
    ContextPackStore,
    context_pack_store_path,
)
from lele_manager.core.vault import write_lesson_markdown


def _write_lesson(
    vault: Path,
    lesson_id: str,
    *,
    body: str,
    lifecycle: str = "active",
) -> None:
    topic = lesson_id.split("/", 1)[0]
    write_lesson_markdown(
        vault,
        lesson_id=lesson_id,
        body=body,
        topic=topic,
        source="test",
        importance=3,
        tags=["context-pack"],
        date="2026-09-19",
        title=lesson_id,
        lifecycle=lifecycle,
    )


def test_create_and_inspect_context_pack_use_active_vault(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "python/current",
        body="Current canonical lesson.",
    )
    _write_lesson(
        context.vault_dir,
        "python/old",
        body="Old canonical lesson.",
        lifecycle="deprecated",
    )

    client = TestClient(server.app)
    response = client.post(
        "/context-packs",
        json={
            "name": "Release investigation",
            "lesson_ids": ["python/old", "python/current"],
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Release investigation"
    assert created["vault_id"] == context.vault_id
    assert created["lesson_ids"] == ["python/old", "python/current"]

    inspected = client.get(f"/context-packs/{created['id']}")

    assert inspected.status_code == 200
    payload = inspected.json()
    assert payload["id"] == created["id"]
    assert payload["name"] == "Release investigation"
    assert [item["lesson_id"] for item in payload["members"]] == [
        "python/old",
        "python/current",
    ]
    assert [item["position"] for item in payload["members"]] == [0, 1]
    assert [item["resolved"] for item in payload["members"]] == [True, True]
    assert payload["members"][0]["lesson"]["lifecycle"] == "deprecated"
    assert payload["members"][1]["lesson"]["lifecycle"] == "active"


def test_create_rejects_missing_member_without_persisting_pack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "python/current",
        body="Current canonical lesson.",
    )

    client = TestClient(server.app)
    response = client.post(
        "/context-packs",
        json={
            "name": "Must fail atomically",
            "lesson_ids": ["python/current", "python/missing"],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "context_pack_member_not_found"

    assert ContextPackStore(context_pack_store_path()).list(
        vault_id=context.vault_id
    ) == ()


def test_inspect_reports_reference_deleted_after_pack_creation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "python/current",
        body="Current canonical lesson.",
    )
    doomed = context.vault_dir / "python" / "doomed.md"
    _write_lesson(
        context.vault_dir,
        "python/doomed",
        body="Will disappear.",
    )

    client = TestClient(server.app)
    created = client.post(
        "/context-packs",
        json={
            "name": "Broken later",
            "lesson_ids": ["python/current", "python/doomed"],
        },
    )
    assert created.status_code == 201

    doomed.unlink()

    inspected = client.get(
        f"/context-packs/{created.json()['id']}"
    )

    assert inspected.status_code == 200
    members = inspected.json()["members"]

    assert [item["lesson_id"] for item in members] == [
        "python/current",
        "python/doomed",
    ]
    assert members[0]["resolved"] is True
    assert members[0]["lesson"] is not None
    assert members[1]["resolved"] is False
    assert members[1]["lesson"] is None


def test_context_pack_crud_and_membership_preserve_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    for lesson_id in (
        "python/one",
        "python/two",
        "python/three",
    ):
        _write_lesson(
            context.vault_dir,
            lesson_id,
            body=f"Canonical {lesson_id}.",
        )

    client = TestClient(server.app)

    created = client.post(
        "/context-packs",
        json={
            "name": "Original",
            "lesson_ids": ["python/one"],
        },
    )
    assert created.status_code == 201
    pack_id = created.json()["id"]

    listed = client.get("/context-packs")
    assert listed.status_code == 200
    assert [pack["id"] for pack in listed.json()] == [pack_id]

    renamed = client.patch(
        f"/context-packs/{pack_id}",
        json={"name": "Renamed"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"
    assert renamed.json()["lesson_ids"] == ["python/one"]

    added = client.post(
        f"/context-packs/{pack_id}/members",
        json={"lesson_ids": ["python/two", "python/three"]},
    )
    assert added.status_code == 200
    assert added.json()["lesson_ids"] == [
        "python/one",
        "python/two",
        "python/three",
    ]

    removed = client.request(
        "DELETE",
        f"/context-packs/{pack_id}/members",
        json={"lesson_ids": ["python/two"]},
    )
    assert removed.status_code == 200
    assert removed.json()["lesson_ids"] == [
        "python/one",
        "python/three",
    ]

    inspected = client.get(f"/context-packs/{pack_id}")
    assert inspected.status_code == 200
    assert [
        member["lesson_id"]
        for member in inspected.json()["members"]
    ] == ["python/one", "python/three"]

    deleted = client.delete(f"/context-packs/{pack_id}")
    assert deleted.status_code == 204

    missing = client.get(f"/context-packs/{pack_id}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "context_pack_not_found"


def test_add_members_validates_entire_batch_before_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "python/one",
        body="Canonical one.",
    )
    _write_lesson(
        context.vault_dir,
        "python/two",
        body="Canonical two.",
    )

    client = TestClient(server.app)

    created = client.post(
        "/context-packs",
        json={
            "name": "Atomic add",
            "lesson_ids": ["python/one"],
        },
    )
    assert created.status_code == 201
    pack_id = created.json()["id"]

    rejected = client.post(
        f"/context-packs/{pack_id}/members",
        json={
            "lesson_ids": [
                "python/two",
                "python/missing",
            ]
        },
    )

    assert rejected.status_code == 404
    assert (
        rejected.json()["detail"]["code"]
        == "context_pack_member_not_found"
    )

    inspected = client.get(f"/context-packs/{pack_id}")
    assert inspected.status_code == 200
    assert inspected.json()["lesson_ids"] == ["python/one"]


def test_context_pack_routes_are_scoped_to_active_vault(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "python/current",
        body="Current.",
    )

    client = TestClient(server.app)
    created = client.post(
        "/context-packs",
        json={
            "name": "Scoped",
            "lesson_ids": ["python/current"],
        },
    )
    assert created.status_code == 201

    pack_id = created.json()["id"]
    store = ContextPackStore(context_pack_store_path())

    other_vault_id = "22222222-2222-4222-8222-222222222222"
    store.create(
        name="Other Vault",
        vault_id=other_vault_id,
        lesson_ids=("python/current",),
    )

    listed = client.get("/context-packs")
    assert listed.status_code == 200
    assert [pack["id"] for pack in listed.json()] == [pack_id]


def test_context_pack_export_uses_canonical_membership_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "python/first",
        body="FIRST UNIQUE BODY.",
        lifecycle="deprecated",
    )
    _write_lesson(
        context.vault_dir,
        "python/second",
        body="SECOND UNIQUE BODY.",
    )

    client = TestClient(server.app)
    created = client.post(
        "/context-packs",
        json={
            "name": "Ordered export",
            "lesson_ids": [
                "python/second",
                "python/first",
            ],
        },
    )
    assert created.status_code == 201
    pack_id = created.json()["id"]

    response = client.get(
        f"/context-packs/{pack_id}/export",
        params={"format": "json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["n_lessons"] == 2

    markdown = payload["markdown"]
    assert markdown.index("SECOND UNIQUE BODY.") < markdown.index(
        "FIRST UNIQUE BODY."
    )
    assert "lifecycle: deprecated" in markdown


def test_context_pack_export_reports_broken_references(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))

    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        "python/current",
        body="CURRENT BODY.",
    )
    _write_lesson(
        context.vault_dir,
        "python/doomed",
        body="DOOMED BODY.",
    )
    doomed = context.vault_dir / "python" / "doomed.md"

    client = TestClient(server.app)
    created = client.post(
        "/context-packs",
        json={
            "name": "Broken export",
            "lesson_ids": [
                "python/current",
                "python/doomed",
            ],
        },
    )
    assert created.status_code == 201
    pack_id = created.json()["id"]

    doomed.unlink()

    response = client.get(
        f"/context-packs/{pack_id}/export",
        params={"format": "json"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "context_pack_has_broken_references"
    assert detail["lesson_ids"] == ["python/doomed"]
