from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from lele_manager.adapters.json_candidate_repository import (
    JsonCandidateRepository,
)
from lele_manager.application.candidate_approval import (
    CandidateApprovalService,
    CanonicalLessonSpec,
    RefreshOutcome,
    VaultWriteOutcome,
)
from lele_manager.application.candidate_review import (
    CandidateReviewService,
)
import lele_manager.application.pkps_import as pkps_import
from lele_manager.application.pkps_import import (
    PkpsConflictError,
    PkpsImportService,
    PkpsPackageError,
    PkpsPersistenceError,
    load_pkps_package,
)
from lele_manager.cli import lele as lele_cli
from lele_manager.cli import pkps as pkps_cli


NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)


def _manifest(
    content: bytes,
    *,
    package_id: str = "gyte:lesson-001",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": package_id,
        "producer": {
            "name": "gyte-study-tools",
            "version": "0.5.0-dev",
        },
        "created_at": "2026-08-06T09:00:00Z",
        "lesson": {
            "path": "lesson.md",
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        },
        "source": {
            "type": "article",
            "url": "https://example.test/article",
            "title": "Synthetic PKPS lesson",
            "external_id": "article-001",
        },
    }


def _write_package(
    root: Path,
    *,
    content: bytes = b"# Synthetic PKPS lesson\n",
    package_id: str = "gyte:lesson-001",
) -> Path:
    root.mkdir()
    (root / "lesson.md").write_bytes(content)
    (root / "pkps-manifest.json").write_text(
        json.dumps(
            _manifest(content, package_id=package_id),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def _service(
    tmp_path: Path,
) -> tuple[PkpsImportService, JsonCandidateRepository]:
    repository = JsonCandidateRepository(tmp_path / "candidates.json")
    return (
        PkpsImportService(repository, lambda: NOW),
        repository,
    )


class RecordingVault:
    def __init__(self) -> None:
        self.lessons: list[CanonicalLessonSpec] = []

    def publish(
        self,
        lesson: CanonicalLessonSpec,
    ) -> VaultWriteOutcome:
        self.lessons.append(lesson)
        return VaultWriteOutcome.CREATED

    def verify(
        self,
        lesson: CanonicalLessonSpec,
    ) -> VaultWriteOutcome:
        self.lessons.append(lesson)
        return VaultWriteOutcome.IDENTICAL


class RecordingRefresh:
    def __init__(self) -> None:
        self.calls = 0

    def refresh(self) -> RefreshOutcome:
        self.calls += 1
        return RefreshOutcome()


def test_rejects_zip_package_path_symlink(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "package.zip"

    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("root/file.txt", "x")

    linked = tmp_path / "linked.zip"
    linked.symlink_to(archive)

    with pytest.raises(
        PkpsPackageError,
        match="must not be a symlink",
    ):
        load_pkps_package(linked)


def test_rejects_directory_manifest_over_resource_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    monkeypatch.setattr(pkps_import, "MAX_MANIFEST_BYTES", 16)

    with pytest.raises(
        PkpsPackageError,
        match="manifest exceeds",
    ):
        load_pkps_package(package)


def test_rejects_directory_lesson_over_resource_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(
        tmp_path / "package",
        content=b"# lesson\n",
    )
    monkeypatch.setattr(pkps_import, "MAX_LESSON_BYTES", 4)

    with pytest.raises(
        PkpsPackageError,
        match="lesson exceeds",
    ):
        load_pkps_package(package)


def test_rejects_zip_entry_count_over_resource_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"# lesson\n"
    archive = tmp_path / "package.zip"

    with zipfile.ZipFile(archive, "w") as target:
        target.writestr(
            "root/pkps-manifest.json",
            json.dumps(_manifest(content)),
        )
        target.writestr("root/lesson.md", content)
        target.writestr("root/extra.txt", "x")

    monkeypatch.setattr(pkps_import, "MAX_ZIP_ENTRIES", 2)

    with pytest.raises(
        PkpsPackageError,
        match="entry limit",
    ):
        load_pkps_package(archive)


def test_rejects_zip_uncompressed_size_over_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"# lesson\n"
    archive = tmp_path / "package.zip"

    with zipfile.ZipFile(archive, "w") as target:
        target.writestr(
            "root/pkps-manifest.json",
            json.dumps(_manifest(content)),
        )
        target.writestr("root/lesson.md", content)

    monkeypatch.setattr(
        pkps_import,
        "MAX_ZIP_UNCOMPRESSED_BYTES",
        8,
    )

    with pytest.raises(
        PkpsPackageError,
        match="uncompressed-size limit",
    ):
        load_pkps_package(archive)


def test_different_package_ids_with_same_content_are_distinct(
    tmp_path: Path,
) -> None:
    content = b"# Shared content\n"
    first_package = _write_package(
        tmp_path / "first",
        content=content,
        package_id="gyte:first",
    )
    second_package = _write_package(
        tmp_path / "second",
        content=content,
        package_id="gyte:second",
    )
    service, repository = _service(tmp_path)

    first = service.import_package(first_package)
    second = service.import_package(second_package)

    assert first.candidate.candidate_id != second.candidate.candidate_id
    assert len(repository.list()) == 2


def test_idempotent_reimport_preserves_original_provenance(
    tmp_path: Path,
) -> None:
    package = _write_package(tmp_path / "package")
    service, repository = _service(tmp_path)

    first = service.import_package(package)
    first_provenance = first.candidate.provenance
    second = service.import_package(package)

    assert second.reused is True
    assert second.candidate.provenance == first_provenance
    assert repository.list() == (first.candidate,)


def test_same_package_id_with_different_content_conflicts(
    tmp_path: Path,
) -> None:
    package = _write_package(tmp_path / "package")
    service, _ = _service(tmp_path)

    service.import_package(package)

    replacement = b"# Changed content\n"
    (package / "lesson.md").write_bytes(replacement)
    (package / "pkps-manifest.json").write_text(
        json.dumps(_manifest(replacement)),
        encoding="utf-8",
    )

    with pytest.raises(PkpsConflictError):
        service.import_package(package)


def test_pkps_provenance_survives_normal_approval(
    tmp_path: Path,
) -> None:
    package = _write_package(tmp_path / "package")
    service, repository = _service(tmp_path)
    imported = service.import_package(package)

    original_pkps = imported.candidate.provenance.run_metadata["pkps"]
    vault = RecordingVault()
    refresh = RecordingRefresh()

    assert vault.lessons == []

    review = CandidateReviewService(repository, lambda: NOW)
    revised = review.revise_candidate(
        imported.candidate.candidate_id,
        expected_revision=0,
        proposed_text=None,
        proposed_metadata={
            "topic": "science",
            "source": "article",
            "importance": 4,
            "tags": ["pkps", "gyte"],
            "date": "2026-08-06",
            "title": "Synthetic PKPS lesson",
        },
        reason="prepare canonical metadata",
    )
    accepted = review.accept_candidate(
        revised.candidate_id,
        expected_revision=revised.revision,
        reason="review complete",
    )

    assert vault.lessons == []

    approval = CandidateApprovalService(
        repository,
        vault,
        refresh,
        lambda: NOW,
    ).approve(
        accepted.candidate_id,
        expected_revision=accepted.revision,
    )

    assert approval.candidate_state_changed is True
    assert len(vault.lessons) == 1
    assert refresh.calls == 1

    canonical_pkps = vault.lessons[0].provenance["run_metadata"]["pkps"]

    assert canonical_pkps["package_id"] == original_pkps["package_id"]
    assert canonical_pkps["schema_version"] == 1
    assert canonical_pkps["producer"] == {
        "name": "gyte-study-tools",
        "version": "0.5.0-dev",
    }
    assert canonical_pkps["source"]["url"] == ("https://example.test/article")
    assert canonical_pkps["lesson_sha256"] == (
        hashlib.sha256(b"# Synthetic PKPS lesson\n").hexdigest()
    )
    assert canonical_pkps["lesson_bytes"] == len(b"# Synthetic PKPS lesson\n")
    assert canonical_pkps["manifest"]["source"]["external_id"] == ("article-001")


def test_cli_unreadable_package_has_controlled_human_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )

    with pytest.raises(SystemExit) as result:
        lele_cli.main(["pkps", "import", str(tmp_path / "missing")])

    captured = capsys.readouterr()

    assert result.value.code == 1
    assert captured.out == ""
    assert "[errore]" in captured.err
    assert "Traceback" not in captured.err


def test_cli_invalid_manifest_has_controlled_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = _write_package(tmp_path / "package")
    (package / "pkps-manifest.json").write_text(
        "{",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )

    with pytest.raises(SystemExit) as result:
        lele_cli.main(["pkps", "import", str(package), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert result.value.code == 1
    assert captured.out == ""
    assert payload["error"]["code"] == "invalid_package"
    assert "Traceback" not in captured.err


def test_cli_package_conflict_has_controlled_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = _write_package(tmp_path / "package")
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )

    with pytest.raises(SystemExit) as first:
        lele_cli.main(["pkps", "import", str(package), "--json"])

    assert first.value.code == 0
    capsys.readouterr()

    replacement = b"# replacement\n"
    (package / "lesson.md").write_bytes(replacement)
    (package / "pkps-manifest.json").write_text(
        json.dumps(_manifest(replacement)),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as second:
        lele_cli.main(["pkps", "import", str(package), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert second.value.code == 1
    assert payload["error"]["code"] == "package_id_conflict"
    assert "Traceback" not in captured.err


def test_cli_storage_failure_has_controlled_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = _write_package(tmp_path / "package")

    def unavailable_repository() -> JsonCandidateRepository:
        raise PkpsPersistenceError("candidate storage configuration is unavailable")

    monkeypatch.setattr(
        pkps_cli,
        "_repository",
        unavailable_repository,
    )

    with pytest.raises(SystemExit) as result:
        lele_cli.main(["pkps", "import", str(package), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert result.value.code == 2
    assert captured.out == ""
    assert payload["error"]["code"] == ("candidate_storage_unavailable")
    assert "Traceback" not in captured.err
