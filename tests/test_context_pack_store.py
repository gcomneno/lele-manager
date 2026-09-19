from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import pytest

from lele_manager.core.context_pack_store import (
    CONTEXT_PACK_STORE_FILENAME,
    ContextPackStore,
    context_pack_store_path,
)


def test_default_path_uses_persistent_application_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path))

    assert context_pack_store_path() == tmp_path / CONTEXT_PACK_STORE_FILENAME


def test_create_persists_identity_vault_scope_and_member_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "context-packs.json"

    created = ContextPackStore(path).create(
        name="Release investigation",
        vault_id="11111111-1111-4111-8111-111111111111",
        lesson_ids=(
            "python/logging",
            "git/recovery",
            "testing/regressions",
        ),
    )

    uuid.UUID(created.id)
    assert created.name == "Release investigation"
    assert created.vault_id == "11111111-1111-4111-8111-111111111111"
    assert created.lesson_ids == (
        "python/logging",
        "git/recovery",
        "testing/regressions",
    )

    created_at = datetime.fromisoformat(created.created_at)
    updated_at = datetime.fromisoformat(created.updated_at)
    assert created_at.utcoffset() is not None
    assert created_at.utcoffset().total_seconds() == 0
    assert updated_at == created_at

    reloaded = ContextPackStore(path).get(created.id)

    assert reloaded == created


@pytest.mark.parametrize(
    ("name", "vault_id", "lesson_ids"),
    [
        ("", "11111111-1111-4111-8111-111111111111", ("python/logging",)),
        ("   ", "11111111-1111-4111-8111-111111111111", ("python/logging",)),
        ("Pack", "", ("python/logging",)),
        ("Pack", "not-a-uuid", ("python/logging",)),
        ("Pack", "11111111-1111-4111-8111-111111111111", ()),
        ("Pack", "11111111-1111-4111-8111-111111111111", ("",)),
        ("Pack", "11111111-1111-4111-8111-111111111111", ("   ",)),
        (
            "Pack",
            "11111111-1111-4111-8111-111111111111",
            ("python/logging", "python/logging"),
        ),
    ],
)
def test_create_rejects_malformed_pack_contract(
    tmp_path: Path,
    name: str,
    vault_id: str,
    lesson_ids: tuple[str, ...],
) -> None:
    from lele_manager.core.context_pack_store import ContextPackStoreError

    store = ContextPackStore(tmp_path / "context-packs.json")

    with pytest.raises(ContextPackStoreError):
        store.create(
            name=name,
            vault_id=vault_id,
            lesson_ids=lesson_ids,
        )

    assert not store.path.exists()


def test_create_normalizes_surrounding_whitespace_without_reordering_members(
    tmp_path: Path,
) -> None:
    store = ContextPackStore(tmp_path / "context-packs.json")

    created = store.create(
        name="  Release investigation  ",
        vault_id="11111111-1111-4111-8111-111111111111",
        lesson_ids=(
            "  testing/regressions  ",
            "python/logging",
            " git/recovery ",
        ),
    )

    assert created.name == "Release investigation"
    assert created.lesson_ids == (
        "testing/regressions",
        "python/logging",
        "git/recovery",
    )


def test_get_is_scoped_to_the_owning_vault(
    tmp_path: Path,
) -> None:
    from lele_manager.core.context_pack_store import ContextPackNotFoundError

    store = ContextPackStore(tmp_path / "context-packs.json")
    created = store.create(
        name="Release investigation",
        vault_id="11111111-1111-4111-8111-111111111111",
        lesson_ids=("python/logging",),
    )

    assert (
        store.get(
            created.id,
            vault_id="11111111-1111-4111-8111-111111111111",
        )
        == created
    )

    with pytest.raises(ContextPackNotFoundError):
        store.get(
            created.id,
            vault_id="22222222-2222-4222-8222-222222222222",
        )


def test_list_is_vault_scoped_and_preserves_creation_order(tmp_path: Path) -> None:
    store = ContextPackStore(tmp_path / "context-packs.json")
    vault_a = "11111111-1111-4111-8111-111111111111"
    vault_b = "22222222-2222-4222-8222-222222222222"

    first = store.create(
        name="First",
        vault_id=vault_a,
        lesson_ids=("topic/a",),
    )
    store.create(
        name="Other Vault",
        vault_id=vault_b,
        lesson_ids=("topic/x",),
    )
    second = store.create(
        name="Second",
        vault_id=vault_a,
        lesson_ids=("topic/b",),
    )

    assert store.list(vault_id=vault_a) == (first, second)


def test_rename_preserves_identity_scope_members_and_creation_time(
    tmp_path: Path,
) -> None:
    store = ContextPackStore(tmp_path / "context-packs.json")
    vault_id = "11111111-1111-4111-8111-111111111111"
    created = store.create(
        name="Old name",
        vault_id=vault_id,
        lesson_ids=("topic/a", "topic/b"),
    )

    renamed = store.rename(
        created.id,
        vault_id=vault_id,
        name="  New name  ",
    )

    assert renamed.id == created.id
    assert renamed.name == "New name"
    assert renamed.vault_id == created.vault_id
    assert renamed.lesson_ids == created.lesson_ids
    assert renamed.created_at == created.created_at
    assert datetime.fromisoformat(renamed.updated_at) >= datetime.fromisoformat(
        created.updated_at
    )
    assert store.get(created.id, vault_id=vault_id) == renamed


def test_add_members_appends_new_members_in_requested_order(tmp_path: Path) -> None:
    store = ContextPackStore(tmp_path / "context-packs.json")
    vault_id = "11111111-1111-4111-8111-111111111111"
    created = store.create(
        name="Pack",
        vault_id=vault_id,
        lesson_ids=("topic/a",),
    )

    updated = store.add_members(
        created.id,
        vault_id=vault_id,
        lesson_ids=(" topic/b ", "topic/c"),
    )

    assert updated.lesson_ids == ("topic/a", "topic/b", "topic/c")
    assert updated.id == created.id
    assert updated.created_at == created.created_at


def test_add_members_rejects_existing_or_duplicate_members_without_mutation(
    tmp_path: Path,
) -> None:
    from lele_manager.core.context_pack_store import ContextPackStoreError

    path = tmp_path / "context-packs.json"
    store = ContextPackStore(path)
    vault_id = "11111111-1111-4111-8111-111111111111"
    created = store.create(
        name="Pack",
        vault_id=vault_id,
        lesson_ids=("topic/a",),
    )
    before = path.read_bytes()

    with pytest.raises(ContextPackStoreError):
        store.add_members(
            created.id,
            vault_id=vault_id,
            lesson_ids=("topic/a", "topic/b"),
        )
    assert path.read_bytes() == before

    with pytest.raises(ContextPackStoreError):
        store.add_members(
            created.id,
            vault_id=vault_id,
            lesson_ids=("topic/b", "topic/b"),
        )
    assert path.read_bytes() == before


def test_remove_members_preserves_survivor_order_and_allows_empty_pack(
    tmp_path: Path,
) -> None:
    store = ContextPackStore(tmp_path / "context-packs.json")
    vault_id = "11111111-1111-4111-8111-111111111111"
    created = store.create(
        name="Pack",
        vault_id=vault_id,
        lesson_ids=("topic/a", "topic/b", "topic/c"),
    )

    updated = store.remove_members(
        created.id,
        vault_id=vault_id,
        lesson_ids=("topic/b",),
    )
    assert updated.lesson_ids == ("topic/a", "topic/c")

    emptied = store.remove_members(
        created.id,
        vault_id=vault_id,
        lesson_ids=("topic/a", "topic/c"),
    )
    assert emptied.lesson_ids == ()


def test_mutations_are_vault_scoped(tmp_path: Path) -> None:
    from lele_manager.core.context_pack_store import ContextPackNotFoundError

    store = ContextPackStore(tmp_path / "context-packs.json")
    owner = "11111111-1111-4111-8111-111111111111"
    other = "22222222-2222-4222-8222-222222222222"
    created = store.create(
        name="Pack",
        vault_id=owner,
        lesson_ids=("topic/a",),
    )

    with pytest.raises(ContextPackNotFoundError):
        store.rename(created.id, vault_id=other, name="Wrong Vault")
    with pytest.raises(ContextPackNotFoundError):
        store.add_members(
            created.id,
            vault_id=other,
            lesson_ids=("topic/b",),
        )
    with pytest.raises(ContextPackNotFoundError):
        store.remove_members(
            created.id,
            vault_id=other,
            lesson_ids=("topic/a",),
        )
    with pytest.raises(ContextPackNotFoundError):
        store.delete(created.id, vault_id=other)

    assert store.get(created.id, vault_id=owner) == created


def test_delete_removes_only_the_requested_pack(tmp_path: Path) -> None:
    from lele_manager.core.context_pack_store import ContextPackNotFoundError

    store = ContextPackStore(tmp_path / "context-packs.json")
    vault_id = "11111111-1111-4111-8111-111111111111"
    first = store.create(
        name="First",
        vault_id=vault_id,
        lesson_ids=("topic/a",),
    )
    second = store.create(
        name="Second",
        vault_id=vault_id,
        lesson_ids=("topic/b",),
    )

    store.delete(first.id, vault_id=vault_id)

    with pytest.raises(ContextPackNotFoundError):
        store.get(first.id, vault_id=vault_id)
    assert store.list(vault_id=vault_id) == (second,)


@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        '{"schema_version": 999, "packs": []}',
        '{"schema_version": 1}',
        '{"schema_version": 1, "packs": {}}',
    ],
)
def test_load_rejects_malformed_store_without_rewriting_it(
    tmp_path: Path,
    payload: str,
) -> None:
    from lele_manager.core.context_pack_store import ContextPackStoreError

    path = tmp_path / "context-packs.json"
    path.write_text(payload, encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ContextPackStoreError):
        ContextPackStore(path).list(
            vault_id="11111111-1111-4111-8111-111111111111"
        )

    assert path.read_bytes() == before


def test_load_rejects_symlink_store(tmp_path: Path) -> None:
    from lele_manager.core.context_pack_store import ContextPackStoreError

    target = tmp_path / "target.json"
    target.write_text(
        '{"schema_version": 1, "packs": []}\n',
        encoding="utf-8",
    )
    path = tmp_path / "context-packs.json"
    path.symlink_to(target)

    with pytest.raises(ContextPackStoreError):
        ContextPackStore(path).list(
            vault_id="11111111-1111-4111-8111-111111111111"
        )


def test_load_rejects_oversized_store(tmp_path: Path) -> None:
    from lele_manager.core.context_pack_store import (
        MAX_BYTES,
        ContextPackStoreError,
    )

    path = tmp_path / "context-packs.json"
    with path.open("wb") as handle:
        handle.truncate(MAX_BYTES + 1)

    with pytest.raises(ContextPackStoreError):
        ContextPackStore(path).list(
            vault_id="11111111-1111-4111-8111-111111111111"
        )


@pytest.mark.parametrize(
    "pack",
    [
        {
            "id": "not-a-uuid",
            "name": "Pack",
            "vault_id": "11111111-1111-4111-8111-111111111111",
            "lesson_ids": ["topic/a"],
            "created_at": "2026-09-19T09:00:00+00:00",
            "updated_at": "2026-09-19T09:00:00+00:00",
        },
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "name": "",
            "vault_id": "11111111-1111-4111-8111-111111111111",
            "lesson_ids": ["topic/a"],
            "created_at": "2026-09-19T09:00:00+00:00",
            "updated_at": "2026-09-19T09:00:00+00:00",
        },
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "name": "Pack",
            "vault_id": "not-a-uuid",
            "lesson_ids": ["topic/a"],
            "created_at": "2026-09-19T09:00:00+00:00",
            "updated_at": "2026-09-19T09:00:00+00:00",
        },
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "name": "Pack",
            "vault_id": "11111111-1111-4111-8111-111111111111",
            "lesson_ids": ["topic/a", "topic/a"],
            "created_at": "2026-09-19T09:00:00+00:00",
            "updated_at": "2026-09-19T09:00:00+00:00",
        },
    ],
)
def test_load_rejects_semantically_invalid_pack(
    tmp_path: Path,
    pack: dict[str, object],
) -> None:
    import json

    from lele_manager.core.context_pack_store import ContextPackStoreError

    path = tmp_path / "context-packs.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packs": [pack],
            }
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()

    with pytest.raises(ContextPackStoreError):
        ContextPackStore(path).list(
            vault_id="11111111-1111-4111-8111-111111111111"
        )

    assert path.read_bytes() == before


def test_load_rejects_non_regular_store(tmp_path: Path) -> None:
    from lele_manager.core.context_pack_store import ContextPackStoreError

    path = tmp_path / "context-packs.json"
    path.mkdir()

    with pytest.raises(ContextPackStoreError):
        ContextPackStore(path).list(
            vault_id="11111111-1111-4111-8111-111111111111"
        )


def test_load_rejects_duplicate_pack_ids(tmp_path: Path) -> None:
    import json

    from lele_manager.core.context_pack_store import ContextPackStoreError

    path = tmp_path / "context-packs.json"
    pack = {
        "id": "33333333-3333-4333-8333-333333333333",
        "name": "Pack",
        "vault_id": "11111111-1111-4111-8111-111111111111",
        "lesson_ids": ["topic/a"],
        "created_at": "2026-09-19T09:00:00+00:00",
        "updated_at": "2026-09-19T09:00:00+00:00",
    }
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packs": [pack, pack],
            }
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()

    with pytest.raises(ContextPackStoreError):
        ContextPackStore(path).list(
            vault_id="11111111-1111-4111-8111-111111111111"
        )

    assert path.read_bytes() == before


def test_atomic_write_failure_preserves_previous_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lele_manager.core.context_pack_store as context_pack_store

    path = tmp_path / "context-packs.json"
    store = ContextPackStore(path)
    vault_id = "11111111-1111-4111-8111-111111111111"

    created = store.create(
        name="Original",
        vault_id=vault_id,
        lesson_ids=("topic/a",),
    )
    before = path.read_bytes()

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(context_pack_store.os, "replace", fail_replace)

    with pytest.raises(context_pack_store.ContextPackStoreError):
        store.rename(
            created.id,
            vault_id=vault_id,
            name="Must not persist",
        )

    assert path.read_bytes() == before


def test_failed_atomic_write_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lele_manager.core.context_pack_store as context_pack_store

    path = tmp_path / "context-packs.json"
    store = ContextPackStore(path)
    vault_id = "11111111-1111-4111-8111-111111111111"

    created = store.create(
        name="Original",
        vault_id=vault_id,
        lesson_ids=("topic/a",),
    )

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(context_pack_store.os, "replace", fail_replace)

    with pytest.raises(context_pack_store.ContextPackStoreError):
        store.rename(
            created.id,
            vault_id=vault_id,
            name="Must not persist",
        )

    assert list(tmp_path.glob(f".{path.name}.*")) == []
