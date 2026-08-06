from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.pkps_import import (
    PkpsConflictError,
    PkpsImportError,
    PkpsImportService,
    PkpsPackageError,
    PkpsValidationError,
    load_pkps_package,
)
from lele_manager.cli import lele as lele_cli


NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)


def _manifest(content: bytes, **changes: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": 1,
        "package_id": "gyte:lesson-001",
        "producer": {"name": "gyte-study-tools", "version": "0.1.0"},
        "created_at": "2026-08-06T09:00:00Z",
        "lesson": {
            "path": "lesson.md",
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        },
        "source": {
            "type": "youtube",
            "url": "https://example.test/watch?v=1",
            "title": "Synthetic",
        },
    }
    document.update(changes)
    return document


def _directory(root: Path, content: bytes = b"# Synthetic lesson\n") -> Path:
    root.mkdir()
    (root / "lesson.md").write_bytes(content)
    (root / "pkps-manifest.json").write_text(
        json.dumps(_manifest(content)), encoding="utf-8"
    )
    return root


def _service(tmp_path: Path) -> tuple[PkpsImportService, JsonCandidateRepository]:
    repository = JsonCandidateRepository(tmp_path / "candidates.json")
    return PkpsImportService(repository, lambda: NOW), repository


def test_imports_directory_as_staged_candidate_with_persistent_provenance(
    tmp_path: Path,
) -> None:
    package = _directory(tmp_path / "package")
    service, repository = _service(tmp_path)

    result = service.import_package(package)

    assert result.reused is False
    assert result.candidate.state.value == "staged"
    assert repository.list() == (result.candidate,)
    pkps = result.candidate.provenance.run_metadata["pkps"]
    assert pkps["package_id"] == "gyte:lesson-001"
    assert pkps["imported_at"] == NOW.isoformat()
    assert pkps["manifest"]["source"]["title"] == "Synthetic"


def test_reimport_is_idempotent_and_package_id_content_conflicts(
    tmp_path: Path,
) -> None:
    package = _directory(tmp_path / "package")
    service, repository = _service(tmp_path)

    first = service.import_package(package)
    second = service.import_package(package)

    assert second.reused is True
    assert second.candidate == first.candidate
    assert len(repository.list()) == 1
    replacement = b"# Changed lesson\n"
    (package / "lesson.md").write_bytes(replacement)
    (package / "pkps-manifest.json").write_text(
        json.dumps(_manifest(replacement)), encoding="utf-8"
    )
    with pytest.raises(PkpsConflictError):
        service.import_package(package)


def test_imports_single_root_zip(tmp_path: Path) -> None:
    content = b"# Zip lesson\n"
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr(
            "pkps-package/pkps-manifest.json", json.dumps(_manifest(content))
        )
        target.writestr("pkps-package/lesson.md", content)

    result = _service(tmp_path)[0].import_package(archive)

    assert result.candidate.text == content.decode()


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"schema_version": 2}, PkpsValidationError),
        ({"producer": {"name": "other", "version": "1"}}, PkpsValidationError),
        (
            {"lesson": {"path": "/lesson.md", "sha256": "0" * 64, "bytes": 1}},
            PkpsValidationError,
        ),
        (
            {"lesson": {"path": "../lesson.md", "sha256": "0" * 64, "bytes": 1}},
            PkpsValidationError,
        ),
        (
            {"lesson": {"path": "missing.md", "sha256": "0" * 64, "bytes": 1}},
            PkpsPackageError,
        ),
        (
            {"lesson": {"path": "lesson.md", "sha256": "0" * 64, "bytes": 1}},
            PkpsValidationError,
        ),
        (
            {
                "lesson": {
                    "path": "lesson.md",
                    "sha256": hashlib.sha256(b"# Synthetic lesson\n").hexdigest(),
                    "bytes": True,
                }
            },
            PkpsValidationError,
        ),
        ({"package_id": ""}, PkpsValidationError),
        ({"source": {"type": "article", "url": "http://["}}, PkpsValidationError),
    ],
)
def test_rejects_invalid_manifest_contract(
    tmp_path: Path, change: dict[str, object], error: type[Exception]
) -> None:
    package = _directory(tmp_path / "package")
    content = (package / "lesson.md").read_bytes()
    manifest = _manifest(content)
    manifest.update(change)
    (package / "pkps-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(error):
        load_pkps_package(package)


def test_rejects_malformed_json_and_external_lesson_symlink(tmp_path: Path) -> None:
    package = _directory(tmp_path / "package")
    (package / "pkps-manifest.json").write_text("{", encoding="utf-8")
    with pytest.raises(PkpsValidationError):
        load_pkps_package(package)

    package = _directory(tmp_path / "surrogate")
    content = (package / "lesson.md").read_bytes()
    manifest = _manifest(content)
    manifest["source"] = {
        "type": "article",
        "url": "https://example.test/a",
        "external_id": "\ud800",
    }
    (package / "pkps-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True), encoding="utf-8"
    )
    with pytest.raises(PkpsValidationError):
        load_pkps_package(package)

    package = _directory(tmp_path / "linked")
    external = tmp_path / "external.md"
    external.write_text("# external\n", encoding="utf-8")
    (package / "lesson.md").unlink()
    (package / "lesson.md").symlink_to(external)
    with pytest.raises(PkpsPackageError):
        load_pkps_package(package)

    package = _directory(tmp_path / "manifest-linked")
    external_manifest = tmp_path / "external-manifest.json"
    external_manifest.write_text("{}", encoding="utf-8")
    (package / "pkps-manifest.json").unlink()
    (package / "pkps-manifest.json").symlink_to(external_manifest)
    with pytest.raises(PkpsPackageError):
        load_pkps_package(package)


def test_rejects_inconsistent_lesson_size(tmp_path: Path) -> None:
    package = _directory(tmp_path / "package")
    content = (package / "lesson.md").read_bytes()
    manifest = _manifest(content)
    manifest["lesson"] = {
        "path": "lesson.md",
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content) + 1,
    }
    (package / "pkps-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PkpsValidationError):
        load_pkps_package(package)


def test_rejects_ambiguous_or_unsafe_zip(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("a/pkps-manifest.json", "{}")
        target.writestr("b/lesson.md", "x")
    with pytest.raises(PkpsPackageError):
        load_pkps_package(archive)


@pytest.mark.parametrize("kind", ["traversal", "duplicate", "symlink"])
def test_rejects_unsafe_zip_entries(tmp_path: Path, kind: str) -> None:
    archive = tmp_path / f"{kind}.zip"
    with zipfile.ZipFile(archive, "w") as target:
        if kind == "traversal":
            target.writestr("root/../pkps-manifest.json", "{}")
        elif kind == "duplicate":
            target.writestr("root/pkps-manifest.json", "{}")
            target.writestr("root/pkps-manifest.json", "{}")
        else:
            link = zipfile.ZipInfo("root/lesson.md")
            link.external_attr = 0o120777 << 16
            target.writestr(link, "outside.md")

    with pytest.raises(PkpsPackageError):
        load_pkps_package(archive)


def test_malformed_boundary_input_raises_only_domain_error(tmp_path: Path) -> None:
    package = _directory(tmp_path / "package")
    (package / "pkps-manifest.json").write_bytes(b"\xff")

    with pytest.raises(PkpsImportError):
        load_pkps_package(package)


def test_cli_emits_human_and_json_without_writing_vault_or_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _directory(tmp_path / "package")
    data = tmp_path / "data"
    vault = tmp_path / "vault"
    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))

    with pytest.raises(SystemExit) as first:
        lele_cli.main(["pkps", "import", str(package)])
    assert first.value.code == 0
    assert "Package PKPS" in capsys.readouterr().out
    assert not vault.exists()
    assert not (data / "lessons.jsonl").exists()

    with pytest.raises(SystemExit) as second:
        lele_cli.main(["pkps", "import", str(package), "--json"])
    assert second.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["package_id"] == "gyte:lesson-001"
    assert payload["candidate_status"] == "staged"
    assert payload["reused"] is True
    assert payload["provenance_available"] is True
