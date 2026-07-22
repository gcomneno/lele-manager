from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.candidate_approval import canonical_lesson_for
from lele_manager.application.lesson_candidate import (
    CandidateRevisionConflictError,
    CandidateState,
    CandidateStorageError,
    DuplicateCandidateIdError,
)
from lele_manager.cli import lele as lele_cli
from lele_manager.cli import tritalele
from lele_manager.core.paths import candidates_path


def run_cli(argv: list[str]) -> int:
    with pytest.raises(SystemExit) as caught:
        lele_cli.main(argv)
    assert isinstance(caught.value.code, int)
    return caught.value.code


@pytest.fixture
def local_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    paths = {
        "data": tmp_path / "data",
        "candidates": tmp_path / "data" / "candidates.json",
        "lessons": tmp_path / "data" / "lessons.jsonl",
        "vault": tmp_path / "vault",
    }
    monkeypatch.setenv("LELE_DATA_DIR", str(paths["data"]))
    monkeypatch.setenv("LELE_VAULT_DIR", str(paths["vault"]))
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    return paths


def parsed_stdout(capsys: pytest.CaptureFixture[str]) -> object:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def create_source(
    tmp_path: Path,
    *,
    name: str = "source.md",
    content: str = "# First\n\nalpha\n\n# Second\n\nbeta\n",
) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def create_one_candidate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    name: str = "one.md",
    content: str = "A useful lesson.\n",
) -> str:
    source = create_source(tmp_path, name=name, content=content)
    assert run_cli(["ingest", "create", str(source), "--json"]) == 0
    payload = parsed_stdout(capsys)
    assert isinstance(payload, dict)
    candidate_ids = payload["candidate_ids"]
    assert isinstance(candidate_ids, list) and len(candidate_ids) == 1
    return str(candidate_ids[0])


def complete_metadata_args() -> list[str]:
    return [
        "--topic",
        "architecture",
        "--source",
        "book",
        "--importance",
        "4",
        "--tag",
        "design",
        "--tag",
        "boundaries",
        "--date",
        "2026-07-22",
        "--title",
        "Ports and Adapters",
    ]


def prepare_candidate_for_approval(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    name: str = "ready.md",
    content: str = "A candidate ready for approval.\n",
) -> str:
    candidate_id = create_one_candidate(
        tmp_path,
        capsys,
        name=name,
        content=content,
    )
    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "0",
            *complete_metadata_args(),
            "--json",
        ]
    ) == 0
    assert parsed_stdout(capsys)["revision"] == 1
    assert run_cli(
        ["candidates", "accept", candidate_id, "--revision", "1", "--json"]
    ) == 0
    assert parsed_stdout(capsys)["revision"] == 2
    return candidate_id


def test_parser_exposes_every_nested_leaf() -> None:
    parser = lele_cli.build_parser()
    invocations = {
        "ingest_preview": ["ingest", "preview", "source.md"],
        "ingest_create": ["ingest", "create", "source.txt"],
        "candidates_list": ["candidates", "list"],
        "candidates_show": ["candidates", "show", "candidate"],
        "candidates_update": [
            "candidates",
            "update",
            "candidate",
            "--revision",
            "0",
            "--text",
            "new",
        ],
        "candidates_accept": [
            "candidates",
            "accept",
            "candidate",
            "--revision",
            "0",
        ],
        "candidates_reject": [
            "candidates",
            "reject",
            "candidate",
            "--revision",
            "0",
        ],
        "candidates_approve": [
            "candidates",
            "approve",
            "candidate",
            "--revision",
            "0",
        ],
    }

    assert "ingest" in parser.format_help()
    assert "candidates" in parser.format_help()
    for command, argv in invocations.items():
        assert parser.parse_args(argv).tritalele_command == command


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["ingest", "--help"], ("preview", "create")),
        (
            ["candidates", "--help"],
            ("list", "show", "update", "accept", "reject", "approve"),
        ),
        (
            ["candidates", "update", "--help"],
            ("--revision", "--text", "--text-file", "--json"),
        ),
    ],
)
def test_nested_help_is_available_at_each_parser_level(
    argv: list[str],
    expected: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_cli(argv) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert all(item in captured.out for item in expected)


def test_update_rejects_inline_and_file_text_before_dispatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    proposed = tmp_path / "proposal.txt"
    proposed.write_text("proposal", encoding="utf-8")

    assert run_cli(
        [
            "candidates",
            "update",
            "candidate",
            "--revision",
            "0",
            "--text",
            "inline",
            "--text-file",
            str(proposed),
        ]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not allowed with argument" in captured.err


@pytest.mark.parametrize(
    ("name", "source_kind"),
    [("notes.md", "markdown"), ("notes.markdown", "markdown"), ("notes.txt", "plain_text")],
)
def test_preview_file_sources_is_read_only_and_deterministic(
    tmp_path: Path,
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
    source_kind: str,
) -> None:
    def forbidden_write(*args: object, **kwargs: object) -> object:
        raise AssertionError("preview must not call a write adapter")

    monkeypatch.setattr(JsonCandidateRepository, "create", forbidden_write)
    monkeypatch.setattr(JsonCandidateRepository, "update", forbidden_write)
    monkeypatch.setattr(
        tritalele.FilesystemCanonicalMarkdownVault, "publish", forbidden_write
    )
    monkeypatch.setattr(
        tritalele.FilesystemCanonicalMarkdownVault, "verify", forbidden_write
    )
    monkeypatch.setattr(tritalele.VaultJsonlRefresh, "refresh", forbidden_write)
    source = create_source(tmp_path, name=name)
    argv = [
        "ingest",
        "preview",
        str(source),
        "--max-characters",
        "16",
        "--json",
    ]

    assert run_cli(argv) == 0
    first = parsed_stdout(capsys)
    assert run_cli(argv) == 0
    second = parsed_stdout(capsys)

    assert isinstance(first, dict) and isinstance(second, dict)
    assert first["source"]["kind"] == source_kind
    assert first["source"]["logical_name"] == name
    assert first["candidate_ids"] == second["candidate_ids"]
    assert first["candidate_ids"] == [
        item["candidate_id"] for item in first["candidates"]
    ]
    assert [
        item["provenance"]["chunk_index"] for item in first["candidates"]
    ] == list(range(len(first["candidates"])))
    assert not local_paths["candidates"].exists()
    assert not local_paths["vault"].exists()
    assert not local_paths["lessons"].exists()
    assert local_paths["data"].is_dir()


def test_preview_stdin_reads_once_without_filesystem_writes(
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class CountingStdin(io.StringIO):
        calls = 0

        def read(self, *args: object, **kwargs: object) -> str:
            self.calls += 1
            return super().read(*args, **kwargs)

    stdin = CountingStdin("stdin lesson\n")
    monkeypatch.setattr(tritalele.sys, "stdin", stdin)

    def forbidden_write(*args: object, **kwargs: object) -> object:
        raise AssertionError("preview must not call a write adapter")

    monkeypatch.setattr(JsonCandidateRepository, "create", forbidden_write)
    monkeypatch.setattr(JsonCandidateRepository, "update", forbidden_write)
    monkeypatch.setattr(
        tritalele.FilesystemCanonicalMarkdownVault, "publish", forbidden_write
    )
    monkeypatch.setattr(
        tritalele.FilesystemCanonicalMarkdownVault, "verify", forbidden_write
    )
    monkeypatch.setattr(tritalele.VaultJsonlRefresh, "refresh", forbidden_write)

    assert run_cli(["ingest", "preview", "-", "--json"]) == 0
    payload = parsed_stdout(capsys)

    assert isinstance(payload, dict)
    assert stdin.calls == 1
    assert payload["source"]["kind"] == "stdin"
    assert payload["source"]["logical_name"] == "stdin"
    assert not local_paths["candidates"].exists()
    assert not local_paths["vault"].exists()
    assert not local_paths["lessons"].exists()
    assert local_paths["data"].is_dir()


def test_preview_preserves_existing_staging_vault_and_projection_bytes(
    tmp_path: Path,
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = create_source(tmp_path)
    local_paths["candidates"].parent.mkdir(parents=True)
    local_paths["candidates"].write_text(
        '{"candidates":[],"schema_version":2}\n', encoding="utf-8"
    )
    vault_file = local_paths["vault"] / "topic" / "lesson.md"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_bytes(b"vault sentinel\n")
    local_paths["lessons"].write_bytes(b"projection sentinel\n")
    protected = (local_paths["candidates"], vault_file, local_paths["lessons"])
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in protected}
    existing_paths = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert run_cli(["ingest", "preview", str(source), "--json"]) == 0
    parsed_stdout(capsys)
    monkeypatch.setattr(tritalele.sys, "stdin", io.StringIO("stdin source\n"))
    assert run_cli(["ingest", "preview", "-", "--json"]) == 0
    parsed_stdout(capsys)

    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in protected
    } == before
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == existing_paths


def test_create_is_idempotent_and_never_writes_vault(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = create_source(tmp_path)
    argv = ["ingest", "create", str(source), "--max-characters", "16", "--json"]

    assert run_cli(argv) == 0
    first = parsed_stdout(capsys)
    assert isinstance(first, dict)
    assert first["created_candidate_ids"] == first["candidate_ids"]
    assert first["skipped_candidate_ids"] == []
    before = local_paths["candidates"].read_bytes()

    assert run_cli(argv) == 0
    second = parsed_stdout(capsys)
    assert isinstance(second, dict)
    assert second["candidate_ids"] == first["candidate_ids"]
    assert second["created_candidate_ids"] == []
    assert second["skipped_candidate_ids"] == first["candidate_ids"]
    assert local_paths["candidates"].read_bytes() == before
    assert not local_paths["vault"].exists()
    assert not local_paths["lessons"].exists()


def test_candidate_path_uses_data_dir_and_ignores_deprecated_lessons_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "configured-data"
    monkeypatch.setenv("LELE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("LELE_DATA_PATH", str(tmp_path / "legacy-lessons.jsonl"))

    assert candidates_path() == data_dir / "candidates.json"


def test_path_resolution_failure_is_a_controlled_configuration_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    loop = tmp_path / "data-loop"
    loop.symlink_to(loop)
    monkeypatch.setenv("LELE_DATA_DIR", str(loop))

    assert run_cli(["candidates", "list", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error"]["code"] == "local_configuration_unavailable"
    assert str(loop) not in captured.err


def test_partial_ingestion_reports_exact_recovery_ids(
    tmp_path: Path,
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = create_source(
        tmp_path,
        content="alpha\n\nbeta\n\ngamma\n",
    )
    argv = ["ingest", "preview", str(source), "--max-characters", "6", "--json"]
    assert run_cli(argv) == 0
    preview = parsed_stdout(capsys)
    candidate_ids = preview["candidate_ids"]
    assert len(candidate_ids) >= 3

    original_create = JsonCandidateRepository.create
    calls = 0

    def fail_second_create(
        self: JsonCandidateRepository, candidate: object
    ) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise CandidateStorageError("private adapter failure")
        return original_create(self, candidate)  # type: ignore[arg-type]

    monkeypatch.setattr(JsonCandidateRepository, "create", fail_second_create)
    assert run_cli(
        ["ingest", "create", str(source), "--max-characters", "6", "--json"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)["error"]
    assert error["code"] == "partial_ingestion"
    assert error["details"] == {
        "created_candidate_ids": candidate_ids[:1],
        "failed_candidate_id": candidate_ids[1],
        "remaining_candidate_ids": candidate_ids[2:],
    }
    assert "private" not in captured.err
    assert [
        item.candidate_id
        for item in JsonCandidateRepository(local_paths["candidates"]).list()
    ] == candidate_ids[:1]


@pytest.mark.parametrize(
    ("repository_error", "expected_exit", "expected_code"),
    [
        (CandidateStorageError("private storage path"), 2, "candidate_storage_unavailable"),
        (DuplicateCandidateIdError("private identity"), 1, "ingestion_conflict"),
    ],
)
def test_initial_ingestion_failures_are_controlled_and_non_mutating(
    tmp_path: Path,
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repository_error: Exception,
    expected_exit: int,
    expected_code: str,
) -> None:
    source = create_source(tmp_path, content="one candidate\n")

    def fail_create(*args: object, **kwargs: object) -> object:
        raise repository_error

    monkeypatch.setattr(JsonCandidateRepository, "create", fail_create)
    assert run_cli(["ingest", "create", str(source), "--json"]) == expected_exit
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == expected_code
    assert "private" not in captured.err
    assert not local_paths["candidates"].exists()
    assert not local_paths["vault"].exists()
    assert not local_paths["lessons"].exists()


def test_list_show_filters_empty_and_malformed_storage_are_controlled(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_cli(["candidates", "list", "--json"]) == 0
    assert parsed_stdout(capsys) == {"count": 0, "candidates": []}

    markdown_id = create_one_candidate(tmp_path, capsys)
    text_id = create_one_candidate(
        tmp_path,
        capsys,
        name="two.txt",
        content="Another useful lesson.\n",
    )
    assert run_cli(["candidates", "list", "--json"]) == 0
    listed = parsed_stdout(capsys)
    assert isinstance(listed, dict)
    assert [item["candidate_id"] for item in listed["candidates"]] == sorted(
        [markdown_id, text_id]
    )

    assert run_cli(
        ["candidates", "list", "--source-kind", "plain_text", "--chunk-index", "0", "--json"]
    ) == 0
    filtered = parsed_stdout(capsys)
    assert isinstance(filtered, dict)
    assert [item["candidate_id"] for item in filtered["candidates"]] == [text_id]

    assert run_cli(["candidates", "show", markdown_id, "--json"]) == 0
    shown = parsed_stdout(capsys)
    assert isinstance(shown, dict)
    assert shown["state"] == "staged"
    assert shown["revision"] == 0
    assert shown["original_text"] == "A useful lesson.\n"
    assert shown["effective_text"] == shown["original_text"]
    assert shown["provenance"]["source_logical_name"] == "one.md"
    assert shown["review_history"] == []

    local_paths["candidates"].write_text("{broken", encoding="utf-8")
    assert run_cli(["candidates", "list", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"]["code"] == "candidate_storage_unavailable"
    assert str(local_paths["candidates"]) not in captured.err


def test_update_revises_once_preserves_source_and_enforces_inputs(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate_id = create_one_candidate(tmp_path, capsys)
    argv = [
        "candidates",
        "update",
        candidate_id,
        "--revision",
        "0",
        "--text",
        "A clearer lesson.",
        *complete_metadata_args(),
        "--reason",
        "prepared",
        "--json",
    ]
    assert run_cli(argv) == 0
    updated = parsed_stdout(capsys)
    assert isinstance(updated, dict)
    assert updated["revision"] == 1
    assert updated["state"] == "staged"
    assert updated["original_text"] == "A useful lesson.\n"
    assert updated["proposed_text"] == "A clearer lesson."
    assert updated["proposed_metadata"] == {
        "topic": "architecture",
        "source": "book",
        "importance": 4,
        "tags": ["design", "boundaries"],
        "date": "2026-07-22",
        "title": "Ports and Adapters",
    }
    provenance = updated["provenance"]

    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "1",
            "--text",
            "Final text.",
            "--json",
        ]
    ) == 0
    text_only = parsed_stdout(capsys)
    assert isinstance(text_only, dict)
    assert text_only["revision"] == 2
    assert text_only["proposed_metadata"] == updated["proposed_metadata"]
    assert text_only["provenance"] == provenance
    assert text_only["original_text"] == updated["original_text"]

    before = local_paths["candidates"].read_bytes()
    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "2",
            "--topic",
            "incomplete",
            "--json",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_cli_input"
    assert local_paths["candidates"].read_bytes() == before

    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "0",
            "--text",
            "stale",
            "--json",
        ]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "stale_candidate_revision"
    assert local_paths["candidates"].read_bytes() == before


def test_metadata_only_update_and_noop_updates_preserve_storage_and_clock(
    tmp_path: Path,
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate_id = create_one_candidate(tmp_path, capsys)
    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "0",
            "--text",
            "A reviewed proposal.",
            "--json",
        ]
    ) == 0
    text_only = parsed_stdout(capsys)
    assert text_only["revision"] == 1
    assert text_only["proposed_metadata"] is None

    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "1",
            *complete_metadata_args(),
            "--json",
        ]
    ) == 0
    metadata_only = parsed_stdout(capsys)
    assert metadata_only["revision"] == 2
    assert metadata_only["proposed_text"] == text_only["proposed_text"]
    before = local_paths["candidates"].read_bytes()

    class CountingClock:
        calls = 0

        def __call__(self) -> object:
            self.calls += 1
            raise AssertionError("a rejected update must not call the clock")

    clock = CountingClock()
    monkeypatch.setattr(tritalele, "_utc_now", clock)

    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "2",
            *complete_metadata_args(),
            "--json",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_candidate_input"
    assert local_paths["candidates"].read_bytes() == before

    assert run_cli(
        ["candidates", "update", candidate_id, "--revision", "2", "--json"]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_cli_input"
    assert local_paths["candidates"].read_bytes() == before

    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "0",
            "--text",
            "stale",
            "--json",
        ]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "stale_candidate_revision"
    assert local_paths["candidates"].read_bytes() == before
    assert clock.calls == 0


def test_accept_reject_transitions_and_revisions_are_explicit(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate_id = create_one_candidate(tmp_path, capsys)

    assert run_cli(
        ["candidates", "accept", candidate_id, "--revision", "0", "--json"]
    ) == 0
    accepted = parsed_stdout(capsys)
    assert accepted == {
        "candidate_id": candidate_id,
        "revision": 1,
        "state": "in_review",
    }
    before = local_paths["candidates"].read_bytes()

    assert run_cli(
        ["candidates", "accept", candidate_id, "--revision", "1", "--json"]
    ) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == (
        "invalid_candidate_transition"
    )
    assert local_paths["candidates"].read_bytes() == before

    assert run_cli(
        [
            "candidates",
            "reject",
            candidate_id,
            "--revision",
            "1",
            "--reason",
            "not suitable",
            "--json",
        ]
    ) == 0
    rejected = parsed_stdout(capsys)
    assert rejected == {
        "candidate_id": candidate_id,
        "revision": 2,
        "state": "rejected",
    }

    assert run_cli(
        ["candidates", "reject", candidate_id, "--revision", "1", "--json"]
    ) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == (
        "stale_candidate_revision"
    )


def test_full_happy_path_approval_refresh_and_idempotency(
    tmp_path: Path,
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = create_source(
        tmp_path,
        name="workflow.md",
        content="# Boundary\n\nKeep application logic out of adapters.\n",
    )

    def forbidden_http_client(*args: object, **kwargs: object) -> object:
        raise AssertionError("local TritaLeLe commands must not create httpx.Client")

    monkeypatch.setattr(lele_cli.httpx, "Client", forbidden_http_client)

    assert run_cli(["ingest", "preview", str(source), "--json"]) == 0
    preview = parsed_stdout(capsys)
    assert isinstance(preview, dict)
    assert not local_paths["candidates"].exists()

    assert run_cli(["ingest", "create", str(source), "--json"]) == 0
    created = parsed_stdout(capsys)
    assert isinstance(created, dict)
    candidate_id = created["candidate_ids"][0]
    assert candidate_id == preview["candidate_ids"][0]
    assert not local_paths["vault"].exists()

    assert run_cli(["candidates", "list", "--state", "staged", "--json"]) == 0
    listed = parsed_stdout(capsys)
    assert listed["candidates"][0]["candidate_id"] == candidate_id
    assert run_cli(["candidates", "show", candidate_id, "--json"]) == 0
    shown = parsed_stdout(capsys)
    assert shown["revision"] == 0

    proposal_file = tmp_path / "proposal.txt"
    proposal_file.write_text("Keep domain logic behind ports.\n", encoding="utf-8")
    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "0",
            "--text-file",
            str(proposal_file),
            *complete_metadata_args(),
            "--json",
        ]
    ) == 0
    assert parsed_stdout(capsys)["revision"] == 1
    assert run_cli(
        ["candidates", "accept", candidate_id, "--revision", "1", "--json"]
    ) == 0
    assert parsed_stdout(capsys)["state"] == "in_review"

    original_refresh = tritalele.VaultJsonlRefresh.refresh

    def checked_refresh(self: object) -> object:
        assert list(local_paths["vault"].rglob("*.md"))
        persisted = JsonCandidateRepository(local_paths["candidates"]).get(candidate_id)
        assert persisted.state is CandidateState.APPROVED
        assert persisted.revision == 3
        return original_refresh(self)  # type: ignore[arg-type]

    monkeypatch.setattr(tritalele.VaultJsonlRefresh, "refresh", checked_refresh)
    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "2", "--json"]
    ) == 0
    approved = parsed_stdout(capsys)
    assert approved["candidate_id"] == candidate_id
    assert approved["candidate_revision"] == 3
    assert approved["vault_write_outcome"] == "created"
    assert approved["candidate_state_changed"] is True
    assert approved["refresh_outcome"] == {"refreshed": True}

    vault_path = local_paths["vault"] / approved["relative_vault_path"]
    assert vault_path.is_file()
    markdown = vault_path.read_text(encoding="utf-8")
    assert "Keep domain logic behind ports." in markdown
    assert local_paths["lessons"].is_file()
    projection_rows = [
        json.loads(line)
        for line in local_paths["lessons"].read_text(encoding="utf-8").splitlines()
    ]
    assert [row["id"] for row in projection_rows] == [approved["lesson_id"]]
    assert JsonCandidateRepository(local_paths["candidates"]).get(
        candidate_id
    ).state is CandidateState.APPROVED

    before_markdown = vault_path.read_bytes()
    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "3", "--json"]
    ) == 0
    repeated = parsed_stdout(capsys)
    assert repeated["candidate_revision"] == 3
    assert repeated["vault_write_outcome"] == "identical"
    assert repeated["candidate_state_changed"] is False
    assert vault_path.read_bytes() == before_markdown

    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "2", "--json"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "stale_candidate_revision"


def test_partial_approval_reports_recovery_data_and_retry_is_idempotent(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate_id = prepare_candidate_for_approval(
        tmp_path,
        capsys,
        name="partial-approval.md",
    )
    local_paths["data"].chmod(0o500)
    try:
        assert run_cli(
            ["candidates", "approve", candidate_id, "--revision", "2", "--json"]
        ) == 1
    finally:
        local_paths["data"].chmod(0o700)
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)["error"]
    assert error["code"] == "partial_approval"
    details = error["details"]
    assert details["candidate_id"] == candidate_id
    assert details["vault_write_outcome"] == "created"
    assert details["candidate_state_changed"] is None
    assert details["refresh_outcome"] == {"refreshed": False}
    assert str(local_paths["data"]) not in captured.err
    assert str(local_paths["vault"]) not in captured.err
    assert (local_paths["vault"] / details["relative_vault_path"]).is_file()
    staged = JsonCandidateRepository(local_paths["candidates"]).get(candidate_id)
    assert staged.state is CandidateState.IN_REVIEW
    assert staged.revision == 2
    assert not local_paths["lessons"].exists()

    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "2", "--json"]
    ) == 0
    recovered = parsed_stdout(capsys)
    assert recovered["candidate_revision"] == 3
    assert recovered["vault_write_outcome"] == "identical"
    assert recovered["candidate_state_changed"] is True
    assert local_paths["lessons"].is_file()


def test_partial_approval_lost_response_does_not_claim_candidate_state(
    tmp_path: Path,
    local_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate_id = prepare_candidate_for_approval(
        tmp_path,
        capsys,
        name="lost-approval-response.md",
    )
    original_update = JsonCandidateRepository.update

    def persist_then_lose_response(
        self: JsonCandidateRepository,
        candidate_id: str,
        candidate: object,
        *,
        expected_revision: int,
    ) -> object:
        original_update(
            self,
            candidate_id,
            candidate,  # type: ignore[arg-type]
            expected_revision=expected_revision,
        )
        raise CandidateRevisionConflictError("private lost response")

    monkeypatch.setattr(
        JsonCandidateRepository,
        "update",
        persist_then_lose_response,
    )
    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "2", "--json"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)["error"]
    assert error["code"] == "partial_approval"
    assert error["details"]["candidate_state_changed"] is None
    assert "candidates show" in error["message"]
    assert "stessa revisione" not in error["message"]
    assert "private" not in captured.err
    persisted = JsonCandidateRepository(local_paths["candidates"]).get(candidate_id)
    assert persisted.state is CandidateState.APPROVED
    assert persisted.revision == 3
    assert not local_paths["lessons"].exists()

    monkeypatch.setattr(JsonCandidateRepository, "update", original_update)
    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "3", "--json"]
    ) == 0
    recovered = parsed_stdout(capsys)
    assert recovered["candidate_state_changed"] is False
    assert recovered["vault_write_outcome"] == "identical"
    assert local_paths["lessons"].is_file()


def test_partial_refresh_json_and_human_output_expose_stable_recovery_data(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate_id = prepare_candidate_for_approval(
        tmp_path,
        capsys,
        name="partial-refresh.md",
    )
    local_paths["lessons"].mkdir()

    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "2", "--json"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)["error"]
    assert error["code"] == "partial_refresh"
    details = error["details"]
    assert details["candidate_id"] == candidate_id
    assert details["candidate_revision"] == 3
    assert details["vault_write_outcome"] == "created"
    assert details["candidate_state_changed"] is True
    assert details["refresh_outcome"] == {"refreshed": False}
    assert str(local_paths["data"]) not in captured.err
    assert str(local_paths["vault"]) not in captured.err
    persisted = JsonCandidateRepository(local_paths["candidates"]).get(candidate_id)
    assert persisted.state is CandidateState.APPROVED
    assert persisted.revision == 3
    assert (local_paths["vault"] / details["relative_vault_path"]).is_file()

    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "3"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[errore]" in captured.err
    for stable_value in (
        candidate_id,
        details["lesson_id"],
        details["relative_vault_path"],
        "candidate_revision: 3",
        "vault_write_outcome: identical",
    ):
        assert str(stable_value) in captured.err
    assert str(local_paths["data"]) not in captured.err
    assert str(local_paths["vault"]) not in captured.err

    local_paths["lessons"].rmdir()
    assert run_cli(
        ["candidates", "approve", candidate_id, "--revision", "3", "--json"]
    ) == 0
    recovered = parsed_stdout(capsys)
    assert recovered["candidate_revision"] == 3
    assert recovered["vault_write_outcome"] == "identical"
    assert recovered["candidate_state_changed"] is False
    assert local_paths["lessons"].is_file()


def test_approval_missing_metadata_and_vault_collision_are_controlled(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_metadata_id = create_one_candidate(tmp_path, capsys, name="missing.md")
    assert run_cli(
        [
            "candidates",
            "accept",
            missing_metadata_id,
            "--revision",
            "0",
            "--json",
        ]
    ) == 0
    parsed_stdout(capsys)
    assert run_cli(
        [
            "candidates",
            "approve",
            missing_metadata_id,
            "--revision",
            "1",
            "--json",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_approval_metadata"
    assert not local_paths["vault"].exists()

    collision_id = create_one_candidate(
        tmp_path, capsys, name="collision.md", content="Collision candidate.\n"
    )
    assert run_cli(
        [
            "candidates",
            "update",
            collision_id,
            "--revision",
            "0",
            *complete_metadata_args(),
            "--json",
        ]
    ) == 0
    parsed_stdout(capsys)
    before_lifecycle = local_paths["candidates"].read_bytes()
    assert run_cli(
        ["candidates", "approve", collision_id, "--revision", "1", "--json"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == (
        "invalid_candidate_transition"
    )
    assert local_paths["candidates"].read_bytes() == before_lifecycle
    assert not local_paths["vault"].exists()
    assert run_cli(
        ["candidates", "accept", collision_id, "--revision", "1", "--json"]
    ) == 0
    parsed_stdout(capsys)

    repository = JsonCandidateRepository(local_paths["candidates"])
    spec = canonical_lesson_for(repository.get(collision_id))
    occupied = local_paths["vault"] / spec.relative_path
    occupied.parent.mkdir(parents=True)
    occupied.write_text("occupied", encoding="utf-8")
    before = local_paths["candidates"].read_bytes()

    assert run_cli(
        ["candidates", "approve", collision_id, "--revision", "2", "--json"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "vault_path_collision"
    assert occupied.read_text(encoding="utf-8") == "occupied"
    assert local_paths["candidates"].read_bytes() == before
    assert not local_paths["lessons"].exists()


@pytest.mark.parametrize(
    ("argv", "expected_code"),
    [
        (["ingest", "preview", "unsupported.pdf", "--json"], "unsupported_source"),
        (
            ["ingest", "preview", "missing.md", "--json"],
            "source_unavailable",
        ),
        (
            [
                "ingest",
                "preview",
                "source.md",
                "--max-characters",
                "0",
                "--json",
            ],
            "invalid_cli_input",
        ),
    ],
)
def test_invalid_ingestion_inputs_have_controlled_json_errors(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    expected_code: str,
) -> None:
    create_source(tmp_path)
    resolved_argv = [str(tmp_path / item) if item == "source.md" else item for item in argv]

    assert run_cli(resolved_argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error"]["code"] == expected_code
    assert not local_paths["candidates"].exists()
    assert not local_paths["vault"].exists()
    assert not local_paths["lessons"].exists()


def test_invalid_utf8_sources_and_proposed_text_files_are_controlled(
    tmp_path: Path,
    local_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid_source = tmp_path / "invalid.txt"
    invalid_source.write_bytes(b"\xff")
    assert run_cli(["ingest", "preview", str(invalid_source), "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_source_encoding"
    assert not local_paths["candidates"].exists()

    candidate_id = create_one_candidate(tmp_path, capsys)
    before = local_paths["candidates"].read_bytes()
    invalid_proposal = tmp_path / "invalid-proposal.txt"
    invalid_proposal.write_bytes(b"\xff")
    assert run_cli(
        [
            "candidates",
            "update",
            candidate_id,
            "--revision",
            "0",
            "--text-file",
            str(invalid_proposal),
            "--json",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_cli_input"
    assert local_paths["candidates"].read_bytes() == before
