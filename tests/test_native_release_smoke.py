from __future__ import annotations

import runpy
import tarfile
import zipfile
from pathlib import Path
from typing import Any

SMOKE: dict[str, Any] = runpy.run_path(
    str(Path("scripts/smoke-native-release.py"))
)

find_release_archive = SMOKE["find_release_archive"]
extract_release_archive = SMOKE["extract_release_archive"]
assert_isolated_runtime_paths = SMOKE["assert_isolated_runtime_paths"]
find_linux_installer = SMOKE["find_linux_installer"]
run_linux_installed_smoke = SMOKE["run_linux_installed_smoke"]


def test_find_release_archive_requires_exactly_one_match(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "LeLe-Manager-v1.2.3-Linux-x86_64.tar.gz"
    archive.write_bytes(b"archive")

    assert find_release_archive(
        tmp_path,
        "1.2.3",
        "Linux",
        ".tar.gz",
    ) == archive


def test_find_release_archive_rejects_ambiguous_matches(
    tmp_path: Path,
) -> None:
    for arch in ("x86_64", "arm64"):
        (
            tmp_path
            / f"LeLe-Manager-v1.2.3-Linux-{arch}.tar.gz"
        ).write_bytes(b"archive")

    try:
        find_release_archive(
            tmp_path,
            "1.2.3",
            "Linux",
            ".tar.gz",
        )
    except RuntimeError as exc:
        assert "esattamente un archive" in str(exc)
    else:
        raise AssertionError("ambiguous release archives accepted")


def test_extract_release_archive_supports_tar_and_zip(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("LeLe Manager", encoding="utf-8")

    tar_path = tmp_path / "release.tar.gz"
    with tarfile.open(tar_path, "w:gz") as stream:
        stream.add(source, arcname="package/source.txt")

    zip_path = tmp_path / "release.zip"
    with zipfile.ZipFile(zip_path, "w") as stream:
        stream.write(source, "package/source.txt")

    tar_target = tmp_path / "tar-target"
    zip_target = tmp_path / "zip-target"

    extract_release_archive(tar_path, tar_target)
    extract_release_archive(zip_path, zip_target)

    assert (tar_target / "package/source.txt").read_text() == "LeLe Manager"
    assert (zip_target / "package/source.txt").read_text() == "LeLe Manager"


def test_zip_extraction_restores_unix_executable_mode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "LeLe-Manager"
    source.write_text("#!/bin/sh\n", encoding="utf-8")
    source.chmod(0o755)

    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.write(source, "package/LeLe-Manager")

    target = tmp_path / "target"
    extract_release_archive(archive, target)

    executable = target / "package" / "LeLe-Manager"
    assert executable.stat().st_mode & 0o777 == 0o755


def test_find_linux_installer_requires_an_executable_at_archive_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "LeLe-Manager-v1.2.3-Linux-x86_64"
    root.mkdir()
    installer = root / "install.sh"
    installer.write_text("#!/bin/sh\n", encoding="utf-8")
    installer.chmod(0o755)

    assert find_linux_installer(tmp_path, "1.2.3") == installer


def test_linux_installed_smoke_is_part_of_the_published_archive_contract() -> None:
    assert callable(run_linux_installed_smoke)


def test_runtime_paths_must_stay_outside_extracted_release(
    tmp_path: Path,
) -> None:
    extraction_root = tmp_path / "published"
    runtime_root = tmp_path / "runtime"

    settings = {
        "paths": [
            {
                "key": key,
                "path": str(runtime_root / key),
            }
            for key in (
                "vault",
                "application_data",
                "lesson_projection",
                "candidate_staging",
                "cache",
                "topic_model",
            )
        ]
    }

    assert_isolated_runtime_paths(
        settings,
        extraction_root,
        runtime_root,
    )


def test_runtime_path_inside_release_is_rejected(
    tmp_path: Path,
) -> None:
    extraction_root = tmp_path / "published"
    runtime_root = tmp_path / "runtime"

    settings = {
        "paths": [
            {
                "key": key,
                "path": str(
                    extraction_root / key
                    if key == "vault"
                    else runtime_root / key
                ),
            }
            for key in (
                "vault",
                "application_data",
                "lesson_projection",
                "candidate_staging",
                "cache",
                "topic_model",
            )
        ]
    }

    try:
        assert_isolated_runtime_paths(
            settings,
            extraction_root,
            runtime_root,
        )
    except RuntimeError as exc:
        assert "dentro il release archive" in str(exc)
    else:
        raise AssertionError("runtime path inside release accepted")

def test_runtime_path_outside_temporary_runtime_is_rejected(
    tmp_path: Path,
) -> None:
    extraction_root = tmp_path / "published"
    runtime_root = tmp_path / "runtime"
    external_root = tmp_path / "external"

    settings = {
        "paths": [
            {
                "key": key,
                "path": str(
                    external_root / key
                    if key == "topic_model"
                    else runtime_root / key
                ),
            }
            for key in (
                "vault",
                "application_data",
                "lesson_projection",
                "candidate_staging",
                "cache",
                "topic_model",
            )
        ]
    }

    try:
        assert_isolated_runtime_paths(
            settings,
            extraction_root,
            runtime_root,
        )
    except RuntimeError as exc:
        assert "non è isolato nel runtime temporaneo" in str(exc)
    else:
        raise AssertionError("external runtime path accepted")
